from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Q, Sum, F, ExpressionWrapper, DecimalField, Count, Min, Max
from django.db import transaction
from decimal import InvalidOperation


from .models import (
    Empresa, Sucursal, CanalCliente, GrupoProveedor, Linea, Articulo, Vendedor,
    Cliente, Promocion, CondicionPromocion, EscalaPromocion, BeneficioPromocion,
    Pedido, DetallePedido, PromocionAplicada
)

from .forms import (
    PromocionModelForm, CondicionPromocionFormSet, EscalaPromocionFormSet, BeneficioDirectoPromocionFormSet, BeneficioEscalaPromocionFormSet
)

from .forms import PromocionModelForm, CondicionPromocionFormSet, EscalaPromocionFormSet, BeneficioDirectoPromocionFormSet


# === UTILIDADES ===
def get_active_promotions_for_pedido(pedido):
    now_date = pedido.fecha
    if hasattr(pedido.fecha, 'date') and callable(pedido.fecha.date):
        now_date = pedido.fecha.date()
    
    print(f"\n--- get_active_promotions_for_pedido para Pedido ID: {pedido.pedido_id} ---")
    print(f"  Fecha del pedido para filtro: {now_date} (Tipo: {type(now_date)})")

    # 1. Filtro base: activa y dentro del rango de fechas
    base_filters = Q(activa=True) & \
                   Q(fecha_inicio__lte=now_date) & \
                   Q(fecha_fin__gte=now_date)
    
    promociones_paso_1 = Promocion.objects.filter(base_filters)
    print(f"  Paso 1 (activa y fecha): {promociones_paso_1.count()} promociones encontradas. Nombres: {[p.nombre for p in promociones_paso_1]}")
    if not promociones_paso_1.exists():
        return Promocion.objects.none()

    # 2. Filtro por Empresa (a través de la sucursal del pedido)
    empresa_filters = Q() 
    if hasattr(pedido.sucursal, 'empresa') and pedido.sucursal.empresa:
        empresa_filters = Q(empresa=pedido.sucursal.empresa)
        print(f"  Paso 2 - Filtro Empresa: {pedido.sucursal.empresa.nombre} (ID: {pedido.sucursal.empresa.empresa_id})")
    else:
        print("  Paso 2 - ADVERTENCIA: Pedido.sucursal no tiene empresa. No se puede filtrar por empresa principal.")
        return Promocion.objects.none()

    promociones_paso_2 = promociones_paso_1.filter(empresa_filters)
    print(f"  Paso 2 (después de filtro empresa): {promociones_paso_2.count()} promociones. Nombres: {[p.nombre for p in promociones_paso_2]}")
    if not promociones_paso_2.exists():
        return Promocion.objects.none()

    # 3. Filtro por Sucursal (de la promoción)
    sucursal_filters = Q(sucursal=pedido.sucursal) | Q(sucursal__isnull=True)
    print(f"  Paso 3 - Filtro Sucursal: {pedido.sucursal.nombre} (ID: {pedido.sucursal.sucursal_id}) o promoción sin sucursal.")
    
    promociones_paso_3 = promociones_paso_2.filter(sucursal_filters)
    print(f"  Paso 3 (después de filtro sucursal): {promociones_paso_3.count()} promociones. Nombres: {[p.nombre for p in promociones_paso_3]}")
    if not promociones_paso_3.exists():
        return Promocion.objects.none()

    # 4. Filtro por Canal del Cliente (del pedido)
    canal_filters = Q()
    if pedido.canal:
        canal_filters = Q(canal_cliente_aplicable=pedido.canal) | Q(canal_cliente_aplicable__isnull=True)
        print(f"  Paso 4 - Filtro Canal Cliente: {pedido.canal.nombre} (ID: {pedido.canal.canal_id}) o promoción sin canal.")
    else:
        canal_filters = Q(canal_cliente_aplicable__isnull=True)
        print("  Paso 4 - Pedido sin canal, filtrando promociones sin canal específico.")
    
    promociones_paso_4 = promociones_paso_3.filter(canal_filters)
    print(f"  Paso 4 (después de filtro canal): {promociones_paso_4.count()} promociones. Nombres: {[p.nombre for p in promociones_paso_4]}")
    if not promociones_paso_4.exists():
        return Promocion.objects.none()

    # 5. Filtro por Tipo de Cliente (del pedido)
    tipo_cliente_filters_applied = Q()
    
    cliente_tipo_actual = None
    if hasattr(pedido.cliente, 'tipo_cliente') and pedido.cliente.tipo_cliente:
        cliente_tipo_actual = pedido.cliente.tipo_cliente.lower()
        print(f"  Paso 5 - Tipo de Cliente del Pedido (normalizado): '{cliente_tipo_actual}'")

        if cliente_tipo_actual == 'todos':
            tipo_cliente_filters_applied = Q(tipo_cliente='todos')
            print(f"    Cliente es tipo 'todos', buscando SOLO promociones para 'todos'. Filtro Q: {tipo_cliente_filters_applied}")
        else:
            tipo_cliente_filters_applied = Q(tipo_cliente=cliente_tipo_actual) | Q(tipo_cliente='todos')
            print(f"    Buscando promociones para tipo '{cliente_tipo_actual}' o 'todos'. Filtro Q: {tipo_cliente_filters_applied}")
    else:
        print(f"  Paso 5 - ADVERTENCIA: Cliente no tiene tipo_cliente definido o es vacío. No se aplicarán promociones basadas en tipo de cliente específico (excepto 'todos' si se decide).")
        tipo_cliente_filters_applied = Q(tipo_cliente='todos')

    print(f"    Promociones ANTES del filtro de tipo cliente ({promociones_paso_4.count()}):")
    for p_temp in promociones_paso_4:
        print(f"      - Promo: '{p_temp.nombre}', Tipo Cliente Promo: '{p_temp.tipo_cliente}'")

    promociones_finales = promociones_paso_4.filter(tipo_cliente_filters_applied).order_by('prioridad', 'nombre')
    print(f"  Paso 5 (después de filtro tipo cliente): {promociones_finales.count()} promociones. Nombres: {[p.nombre for p in promociones_finales]}")
    print(f"--- Fin get_active_promotions_for_pedido ---")
    return promociones_finales


def calculate_condition_totals(pedido_detalles, promocion):
    """
    Calcula la cantidad total y el monto total de los productos en un pedido
    que cumplen con las condiciones de una promoción.
    """
    monto_total_condicion = Decimal('0.00')
    cantidad_total_condicion = 0
    items_que_cumplen_condicion = [] 

    condiciones_promo = promocion.condiciones.all()
    if not condiciones_promo.exists() and promocion.aplica_por == 'productos_condicion':
        return Decimal('0.00'), 0, [] 

    if promocion.aplica_por == 'total_pedido':
        monto_total_condicion = sum(d.subtotal_linea for d in pedido_detalles if not d.es_bonificacion)
        cantidad_total_condicion = sum(d.cantidad for d in pedido_detalles if not d.es_bonificacion)
        items_que_cumplen_condicion = [d for d in pedido_detalles if not d.es_bonificacion]
        return monto_total_condicion, cantidad_total_condicion, items_que_cumplen_condicion

    articulos_en_condicion_ids = set()
    lineas_en_condicion_ids = set()
    grupos_en_condicion_ids = set()

    for cond in condiciones_promo:
        if cond.articulo:
            articulos_en_condicion_ids.add(cond.articulo_id)
        if cond.linea:
            lineas_en_condicion_ids.add(cond.linea_id)
        if cond.grupo:
            grupos_en_condicion_ids.add(cond.grupo_id)

    for detalle in pedido_detalles:
        if detalle.es_bonificacion:
            continue

        cumple_alguna_condicion_de_producto = False
        if detalle.articulo_id in articulos_en_condicion_ids:
            cumple_alguna_condicion_de_producto = True
        if detalle.articulo.linea_id in lineas_en_condicion_ids:
            cumple_alguna_condicion_de_producto = True
        if detalle.articulo.grupo_id in grupos_en_condicion_ids:
            cumple_alguna_condicion_de_producto = True
        
        if not (articulos_en_condicion_ids or lineas_en_condicion_ids or grupos_en_condicion_ids) and \
           promocion.aplica_por == 'productos_condicion':
            cumple_alguna_condicion_de_producto = True

        if cumple_alguna_condicion_de_producto:
            monto_total_condicion += detalle.subtotal_linea
            cantidad_total_condicion += detalle.cantidad
            items_que_cumplen_condicion.append(detalle)
            
    return monto_total_condicion, cantidad_total_condicion, items_que_cumplen_condicion


def check_conjunto_obligatorio(pedido_detalles, promocion):
    """Verifica si se cumplen todas las condiciones obligatorias para una promo de conjunto."""
    if promocion.aplica_por != 'conjunto_obligatorio':
        return True 

    condiciones_obligatorias = promocion.condiciones.filter(obligatoria_en_conjunto=True)
    if not condiciones_obligatorias.exists():
        return False

    for cond_obl in condiciones_obligatorias:
        encontrado_en_pedido = False
        for detalle in pedido_detalles:
            if detalle.es_bonificacion:
                continue
            
            cumple_item_condicion = False
            if cond_obl.articulo and detalle.articulo_id == cond_obl.articulo_id:
                cumple_item_condicion = True
            elif cond_obl.linea and detalle.articulo.linea_id == cond_obl.linea_id:
                cumple_item_condicion = True
            elif cond_obl.grupo and detalle.articulo.grupo_id == cond_obl.grupo_id:
                cumple_item_condicion = True
            
            if cumple_item_condicion:
                if cond_obl.cantidad_minima and detalle.cantidad < cond_obl.cantidad_minima:
                    return False 
                encontrado_en_pedido = True
                break 
        
        if not encontrado_en_pedido:
            return False 
            
    return True 


# === MOTOR DE PROMOCIONES ===
@login_required
@transaction.atomic
def procesar_y_aplicar_promociones_a_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, pedido_id=pedido_id)
    print(f"\n--- PROCESANDO PROMOCIONES PARA PEDIDO: {pedido.pedido_id} ---")
    print(f"Cliente: {pedido.cliente.nombres}, Canal: {pedido.canal.nombre}, Sucursal: {pedido.sucursal.nombre}, Fecha: {pedido.fecha}")

    # 1. Limpiar promociones aplicadas anteriormente y revertir efectos
    PromocionAplicada.objects.filter(pedido=pedido).delete()
    DetallePedido.objects.filter(pedido=pedido, es_bonificacion=True).delete()
    
    # Resetear descuentos en líneas existentes (no bonificadas)
    for detalle in pedido.detalles.filter(es_bonificacion=False):
        detalle.descuento_linea = Decimal('0.00')
        detalle.save()
    
    pedido.descuento_total = Decimal('0.00')

    # 2. Obtener detalles activos (no bonificaciones) del pedido para evaluación
    pedido_detalles_activos = list(pedido.detalles.filter(es_bonificacion=False))
    if not pedido_detalles_activos:
        print("No hay detalles activos en el pedido para aplicar promociones.")
        messages.info(request, "El pedido está vacío, no se aplicaron nuevas promociones.")
        pedido.subtotal = sum(d.subtotal_linea for d in pedido.detalles.filter(es_bonificacion=False))
        pedido.total_pedido = pedido.subtotal - pedido.descuento_total 
        pedido.save()
        return redirect('vista_detalle_pedido', pedido_id=pedido.pedido_id)

    print(f"Detalles activos del pedido (antes de aplicar promos): {len(pedido_detalles_activos)} items")
    for d_act in pedido_detalles_activos:
        print(f"  - Art: {d_act.articulo.codigo_articulo}, Cant: {d_act.cantidad}, Subtotal (modelo): {d_act.subtotal_linea}")

    # 3. Obtener promociones candidatas
    promociones_candidatas = get_active_promotions_for_pedido(pedido)
    print(f"Promociones candidatas encontradas ({len(promociones_candidatas)}): {[p.nombre for p in promociones_candidatas] if promociones_candidatas else 'Ninguna'}")

    promociones_efectivamente_aplicadas_objs = []

    for promo in promociones_candidatas:
        print(f"\nEvaluando Promoción: '{promo.nombre}' (ID: {promo.promocion_id})")
        print(f"  Tipo: {promo.get_tipo_display()}, Aplica por: {promo.get_aplica_por_display()}, Escalonada: {promo.es_escalonada}, Prop. Directa: {promo.es_proporcional_directa}")
        if promo.es_proporcional_directa:
            print(f"  Base Cant. Prop. Directa: {promo.base_cantidad_proporcional_directa}, Base Monto Prop. Directa: {promo.base_monto_proporcional_directa}")
        
        monto_condicion, cantidad_condicion, items_condicion = calculate_condition_totals(pedido_detalles_activos, promo)
        print(f"  Resultado de calculate_condition_totals:")
        print(f"    Monto Condición (calculado): {monto_condicion}, Cantidad Condición (calculada): {cantidad_condicion}")
        print(f"    Items en condición ({len(items_condicion)}): {[item.articulo.codigo_articulo for item in items_condicion] if items_condicion else 'Ninguno'}")

        if promo.aplica_por == 'conjunto_obligatorio':
            cumple_conjunto = check_conjunto_obligatorio(pedido_detalles_activos, promo)
            print(f"  Verificación de conjunto obligatorio: {cumple_conjunto}")
            if not cumple_conjunto:
                print(f"  NO CUMPLE CONJUNTO OBLIGATORIO. Saltando promo.")
                continue
        
        beneficios_a_aplicar_config = [] 
        escala_que_aplico = None

        if promo.es_escalonada:
            print("  La promoción ES ESCALONADA.")
            escalas_promo = promo.escalas.order_by('-desde_cantidad', '-desde_monto') 
            for escala in escalas_promo:
                print(f"    Evaluando Escala: '{escala.descripcion_escala}' (DesdeCant: {escala.desde_cantidad}, HastaCant: {escala.hasta_cantidad}, DesdeMonto: {escala.desde_monto}, HastaMonto: {escala.hasta_monto})")
                cumple_esta_escala = False
                if escala.desde_cantidad is not None:
                    if cantidad_condicion >= escala.desde_cantidad and (escala.hasta_cantidad is None or cantidad_condicion <= escala.hasta_cantidad):
                        cumple_esta_escala = True
                elif escala.desde_monto is not None:
                     if monto_condicion >= escala.desde_monto and (escala.hasta_monto is None or monto_condicion <= escala.hasta_monto):
                        cumple_esta_escala = True
                
                print(f"    ¿Cumple esta escala?: {cumple_esta_escala}")
                if cumple_esta_escala:
                    escala_que_aplico = escala
                    multiplicador_benef_escala = 1
                    if escala.proporcional:
                        print(f"      Escala proporcional: BaseCant={escala.base_cantidad_proporcional_escala}, BaseMonto={escala.base_monto_proporcional_escala}")
                        temp_multiplicador = 0
                        if escala.base_cantidad_proporcional_escala and cantidad_condicion >= escala.base_cantidad_proporcional_escala:
                            temp_multiplicador = cantidad_condicion // escala.base_cantidad_proporcional_escala
                        elif escala.base_monto_proporcional_escala and monto_condicion >= escala.base_monto_proporcional_escala:
                            temp_multiplicador = int(monto_condicion // escala.base_monto_proporcional_escala)
                        
                        if temp_multiplicador > 0:
                            multiplicador_benef_escala = temp_multiplicador
                        else:
                            print("      Multiplicador de escala proporcional es 0. No aplica beneficios de esta escala.")
                            continue 


                    print(f"      Multiplicador para beneficios de esta escala: {multiplicador_benef_escala}")
                    for beneficio_obj in escala.beneficios.all():
                        beneficios_a_aplicar_config.append((beneficio_obj, multiplicador_benef_escala))
                    break 
        
        else: 
            print("  La promoción NO ES ESCALONADA.")
            aplica_promo_no_escalonada_base = False
            multiplicador_final_no_escalonada = 1

            if promo.es_proporcional_directa:
                print(f"    Es proporcional directa. BaseCant={promo.base_cantidad_proporcional_directa}, CantCond={cantidad_condicion}")
                temp_multiplicador = 0
                if promo.base_cantidad_proporcional_directa and cantidad_condicion >= promo.base_cantidad_proporcional_directa:
                    temp_multiplicador = cantidad_condicion // promo.base_cantidad_proporcional_directa
                elif promo.base_monto_proporcional_directa and monto_condicion >= promo.base_monto_proporcional_directa:
                    temp_multiplicador = int(monto_condicion // promo.base_monto_proporcional_directa)
                
                if temp_multiplicador > 0:
                    multiplicador_final_no_escalonada = temp_multiplicador
                    aplica_promo_no_escalonada_base = True
                print(f"    Proporcional: aplica_base={aplica_promo_no_escalonada_base}, multiplicador={multiplicador_final_no_escalonada}")

            else: 
                if promo.aplica_por == 'productos_condicion':
                    cond_directa = promo.condiciones.first() 
                    if cond_directa:
                        print(f"    No proporcional. Evaluando umbrales de CondicionPromocion ID {cond_directa.condicionpromocion_id}: CantMin={cond_directa.cantidad_minima}, MontoMin={cond_directa.monto_minimo}")
                        if (cond_directa.cantidad_minima is None or cantidad_condicion >= cond_directa.cantidad_minima) and \
                           (cond_directa.monto_minimo is None or monto_condicion >= cond_directa.monto_minimo):
                            aplica_promo_no_escalonada_base = True
                    elif not cond_directa and (cantidad_condicion > 0 or monto_condicion > Decimal('0.00')):
                        print(f"    No proporcional, sin condición específica, pero hay items en condición. Aplicando.")
                        aplica_promo_no_escalonada_base = True
                
                elif promo.aplica_por == 'total_pedido' or promo.aplica_por == 'conjunto_obligatorio':
                    aplica_promo_no_escalonada_base = True
                print(f"    No proporcional: aplica_base={aplica_promo_no_escalonada_base}")
            
            if aplica_promo_no_escalonada_base:
                beneficios_db = list(promo.beneficios_directos.all())
                if beneficios_db:
                    for beneficio_obj in beneficios_db:
                        beneficios_a_aplicar_config.append((beneficio_obj, multiplicador_final_no_escalonada))
                    print(f"    Beneficios directos a considerar (multiplicador {multiplicador_final_no_escalonada}): {[str(b[0]) for b in beneficios_a_aplicar_config]}")
                else:
                    print("    No hay beneficios directos definidos para esta promoción.")
            else:
                print("    NO CUMPLE CONDICIONES para promo no escalonada o multiplicador proporcional fue 0.")
        

        if not beneficios_a_aplicar_config:
            print(f"  No hay beneficios configurados para aplicar para '{promo.nombre}'. Saltando.")
            continue

        # Aplicar los beneficios recolectados
        print(f"  Aplicando {len(beneficios_a_aplicar_config)} tipo(s) de beneficio para '{promo.nombre}'")
        descripcion_beneficios_str_list_para_esta_promo = []
        monto_descuento_generado_por_esta_promo = Decimal('0.00')

        for beneficio_obj, multiplicador_aplicable in beneficios_a_aplicar_config:
            print(f"    Procesando Beneficio: Tipo={beneficio_obj.get_tipo_display()}, ArtBonif={beneficio_obj.articulo_bonificado}, CantBonif={beneficio_obj.cantidad_bonificada}, %Desc={beneficio_obj.porcentaje_descuento}, Multiplicador={multiplicador_aplicable}")
            if multiplicador_aplicable == 0:
                print("      Multiplicador es 0, omitiendo este beneficio específico.")
                continue

            if beneficio_obj.tipo == 'bonificacion' and beneficio_obj.articulo_bonificado and beneficio_obj.cantidad_bonificada:
                cantidad_a_bonificar_final = beneficio_obj.cantidad_bonificada * multiplicador_aplicable
                print(f"      Cantidad a bonificar: {cantidad_a_bonificar_final}")
                if cantidad_a_bonificar_final > 0:
                    DetallePedido.objects.create(
                        pedido=pedido,
                        articulo=beneficio_obj.articulo_bonificado,
                        cantidad=cantidad_a_bonificar_final,
                        precio_unitario_lista=Decimal('0.00'),
                        subtotal_linea=Decimal('0.00'),
                        descuento_linea=Decimal('0.00'),
                        total_linea=Decimal('0.00'),
                        es_bonificacion=True,
                        promocion_origen=promo
                    )
                    descripcion_beneficios_str_list_para_esta_promo.append(
                        f"{cantidad_a_bonificar_final}x {beneficio_obj.articulo_bonificado.codigo_articulo} (Bonif.)"
                    )
                    print(f"      BONIFICACIÓN CREADA: {cantidad_a_bonificar_final} x {beneficio_obj.articulo_bonificado.codigo_articulo}")

            elif beneficio_obj.tipo == 'descuento' and beneficio_obj.porcentaje_descuento:
                
                items_sobre_los_que_aplicar_descuento = items_condicion 
                if promo.aplica_por == 'total_pedido':
                    items_sobre_los_que_aplicar_descuento = pedido_detalles_activos
                
                print(f"      Aplicando {beneficio_obj.porcentaje_descuento}% de descuento sobre {len(items_sobre_los_que_aplicar_descuento)} items.")
                for item_detalle_activo in items_sobre_los_que_aplicar_descuento:
                    if item_detalle_activo.es_bonificacion: continue

                    # El subtotal_linea será 0 si no hay precios. El descuento será 0.
                    descuento_calculado_para_item = item_detalle_activo.subtotal_linea * (beneficio_obj.porcentaje_descuento / Decimal('100'))
                    descuento_calculado_para_item = descuento_calculado_para_item.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    
                    # Aplicar descuento si es positivo y no excede el valor restante del item
                    if descuento_calculado_para_item > Decimal('0.00') and \
                       (item_detalle_activo.subtotal_linea - item_detalle_activo.descuento_linea - descuento_calculado_para_item >= Decimal('0.00')):
                        
                        # Actualizar el objeto DetallePedido directamente (ya está guardado)
                        detalle_a_actualizar = DetallePedido.objects.get(detallepedido_id=item_detalle_activo.detallepedido_id)
                        detalle_a_actualizar.descuento_linea += descuento_calculado_para_item
                        detalle_a_actualizar.total_linea = detalle_a_actualizar.subtotal_linea - detalle_a_actualizar.descuento_linea
                        detalle_a_actualizar.save()
                        
                        monto_descuento_generado_por_esta_promo += descuento_calculado_para_item
                        print(f"        Descuento de S/{descuento_calculado_para_item} aplicado a item {detalle_a_actualizar.articulo.codigo_articulo}")
                
                if monto_descuento_generado_por_esta_promo > Decimal('0.00'):
                     descripcion_beneficios_str_list_para_esta_promo.append(
                        f"{beneficio_obj.porcentaje_descuento}% Desc. (Total S/ {monto_descuento_generado_por_esta_promo.quantize(Decimal('0.01'))})"
                    )
        
        if descripcion_beneficios_str_list_para_esta_promo:
            promo_aplicada_obj = PromocionAplicada.objects.create(
                pedido=pedido,
                promocion=promo,
                escala_aplicada=escala_que_aplico, 
                descripcion_beneficios_obtenidos=", ".join(descripcion_beneficios_str_list_para_esta_promo),
                monto_descuento_generado=monto_descuento_generado_por_esta_promo
            )
            promociones_efectivamente_aplicadas_objs.append(promo_aplicada_obj) 
            pedido.descuento_total += monto_descuento_generado_por_esta_promo
            print(f"  PROMOCIÓN '{promo.nombre}' APLICADA. Beneficios: {', '.join(descripcion_beneficios_str_list_para_esta_promo)}. Descuento total de esta promo: {monto_descuento_generado_por_esta_promo}")
        else:
            print(f"  No se generaron beneficios concretos (descripción vacía) para la promoción '{promo.nombre}' aunque cumplió condiciones iniciales.")

    # 4. Recalcular totales finales del pedido y guardar
    detalles_finales_del_pedido_con_bonificaciones = pedido.detalles.all()
    pedido.subtotal = sum(d.subtotal_linea for d in detalles_finales_del_pedido_con_bonificaciones if not d.es_bonificacion)
    pedido.total_pedido = pedido.subtotal - pedido.descuento_total
    pedido.save() 
    print(f"Pedido FINAL guardado: ID={pedido.pedido_id}, Subtotal={pedido.subtotal}, DescuentoTotal={pedido.descuento_total}, TotalPedido={pedido.total_pedido}")

    if promociones_efectivamente_aplicadas_objs:
        messages.success(request, f"Se aplicaron {len(promociones_efectivamente_aplicadas_objs)} promoción(es) al pedido.")
    else:
        messages.info(request, "Ninguna promoción fue aplicable a este pedido o no generaron beneficios concretos.")
    
    print(f"--- FIN PROCESAMIENTO PROMOCIONES PARA PEDIDO: {pedido.pedido_id} ---")
    return redirect('vista_detalle_pedido', pedido_id=pedido.pedido_id)


# === PÁGINA PRINCIPAL ===
def home(request):
    return render(request, 'core/home.html')

# === AUTENTICACIÓN ===
def login_user(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, "Sesión iniciada correctamente.")
            return redirect('listar_promociones')
        else:
            messages.error(request, "Nombre de usuario o contraseña incorrectos.")
            return redirect('login_user') 
    return render(request, 'core/login/login.html') 

def logout_user(request):
    logout(request)
    messages.success(request, "Sesión cerrada correctamente.")
    return redirect('home')

def dashboard(request):

    return render(request, 'core/dashboard.html')

# === CRUD PROMOCIONES ===

@login_required
def listar_promociones(request):
    promociones = Promocion.objects.all().order_by('-activa', 'prioridad', 'nombre')
    return render(request, 'core/promociones/listar_promociones.html', {'promociones': promociones})

@login_required
def crear_promocion(request):
    if request.method == 'POST':
        form = PromocionModelForm(request.POST) 
        if form.is_valid():
            promocion = form.save()
            messages.success(request, f"Promoción '{promocion.nombre}' creada. Agregue condiciones, escalas y beneficios.")
            return redirect('detalle_promocion', promocion_id=promocion.promocion_id)
        else:
            messages.error(request, "Por favor corrija los errores en el formulario.")
    else:
        form = PromocionModelForm() 
    return render(request, 'core/promociones/formulario_promocion.html', {'form': form, 'action': 'Crear'})

@login_required
def editar_promocion(request, promocion_id):
    promocion = get_object_or_404(Promocion, promocion_id=promocion_id)
    if request.method == 'POST':
        form = PromocionModelForm(request.POST, instance=promocion) 
        if form.is_valid():
            form.save()
            messages.success(request, f"Promoción '{promocion.nombre}' actualizada.")
            return redirect('detalle_promocion', promocion_id=promocion.promocion_id)
        else:
            messages.error(request, "Por favor corrija los errores en el formulario.")
    else:
        form = PromocionModelForm(instance=promocion) 
    return render(request, 'core/promociones/formulario_promocion.html', {'form': form, 'promocion': promocion, 'action': 'Editar'})

@login_required
def detalle_promocion(request, promocion_id):
    promocion = get_object_or_404(Promocion, promocion_id=promocion_id)
    condiciones = promocion.condiciones.all()
    escalas = promocion.escalas.all() 
    beneficios_directos = promocion.beneficios_directos.all() 

    context = {
        'promocion': promocion,
        'condiciones': condiciones,
        'escalas': escalas,
        'beneficios_directos': beneficios_directos,
    }
    return render(request, 'core/promociones/detalle_promocion.html', context)

@login_required
def gestionar_promocion_completa(request, promocion_id=None):
    if promocion_id:
        promocion = get_object_or_404(Promocion, promocion_id=promocion_id)
        action_text = "Editar"
    else:
        promocion = None
        action_text = "Crear"

    if request.method == 'POST':
        form_promocion = PromocionModelForm(request.POST, instance=promocion, prefix="promo")
        formset_condiciones = CondicionPromocionFormSet(request.POST, instance=promocion, prefix="cond")
        formset_escalas = EscalaPromocionFormSet(request.POST, instance=promocion, prefix="escala")
        formset_beneficios_directos = BeneficioDirectoPromocionFormSet(request.POST, instance=promocion, prefix="benef_directo")

        are_all_valid = (
            form_promocion.is_valid() and
            formset_condiciones.is_valid() and
            formset_escalas.is_valid() and 
            formset_beneficios_directos.is_valid()
        )

        if are_all_valid:
            try:
                with transaction.atomic():
                    nueva_promocion = form_promocion.save()

                    formset_condiciones.instance = nueva_promocion
                    formset_condiciones.save()
                    
                    if nueva_promocion.es_escalonada:
                        formset_escalas.instance = nueva_promocion
                        formset_escalas.save() 
                        
                        if promocion and not promocion.es_escalonada:
                            BeneficioPromocion.objects.filter(promocion=nueva_promocion, escala__isnull=True).delete()
                    else: 
                        formset_beneficios_directos.instance = nueva_promocion
                        formset_beneficios_directos.save()
                        if promocion and promocion.es_escalonada: 
                            EscalaPromocion.objects.filter(promocion=nueva_promocion).delete()
                    
                    messages.success(request, f"Promoción '{nueva_promocion.nombre}' {action_text.lower()}da correctamente.")
                    return redirect('detalle_promocion', promocion_id=nueva_promocion.promocion_id)
            except Exception as e:
                messages.error(request, f"Ocurrió un error al guardar: {e}")
                print(f"Error en transacción de guardar promoción: {e}")
        else:
            messages.error(request, "Por favor corrija los errores en el formulario.")


    else: 
        form_promocion = PromocionModelForm(instance=promocion, prefix="promo")
        formset_condiciones = CondicionPromocionFormSet(instance=promocion, prefix="cond")
        formset_escalas = EscalaPromocionFormSet(instance=promocion, prefix="escala")
        formset_beneficios_directos = BeneficioDirectoPromocionFormSet(instance=promocion, prefix="benef_directo")

    context = {
        'form_promocion': form_promocion,
        'formset_condiciones': formset_condiciones,
        'formset_escalas': formset_escalas,
        'formset_beneficios_directos': formset_beneficios_directos,
        'promocion': promocion,
        'action_text': action_text
    }
    return render(request, 'core/promociones/gestionar_promocion_completa.html', context)

@login_required
def eliminar_promocion(request, promocion_id):
    promocion = get_object_or_404(Promocion, promocion_id=promocion_id)
    if request.method == 'POST':
        nombre_promo = promocion.nombre
        promocion.delete()
        messages.success(request, f"Promoción '{nombre_promo}' eliminada correctamente.")
        return redirect('listar_promociones')
    return render(request, 'core/promociones/confirmar_eliminar_promocion.html', {'promocion': promocion})


# === VISTAS PARA CREAR/GESTIONAR CONDICIONES, ESCALAS, BENEFICIOS ===

@login_required
def gestionar_condiciones_promocion(request, promocion_id):
    promocion = get_object_or_404(Promocion, promocion_id=promocion_id)
    CondicionFormSet = CondicionPromocionFormSet 
    
    if request.method == 'POST':
        formset = CondicionFormSet(request.POST, instance=promocion)
        if formset.is_valid():
            formset.save()
            messages.success(request, "Condiciones actualizadas.")
            return redirect('detalle_promocion', promocion_id=promocion.promocion_id)
    else:
        formset = CondicionFormSet(instance=promocion)
        
    return render(request, 'core/promociones/gestionar_condiciones.html', {'promocion': promocion, 'formset': formset})


# === CRUD PEDIDOS ===
@login_required
def listar_pedidos(request):
    pedidos = Pedido.objects.all().order_by('-fecha')
    return render(request, 'core/pedidos/listar_pedidos.html', {'pedidos': pedidos})

@login_required
def crear_pedido_vista(request):
    if request.method == "POST":
        cliente_id_from_form = request.POST.get("cliente")
        canal_id_from_form = request.POST.get("canal_cliente")
        sucursal_id_from_form = request.POST.get("sucursal")
        
        articulo_pks_from_form = request.POST.getlist("articulo_pk[]")
        cantidades_from_form = request.POST.getlist("cantidad[]")
        precios_unitarios_from_form = request.POST.getlist("precio_unitario[]")

        # --- Validaciones de cabecera y de que las listas tengan la misma longitud ---
        if not cliente_id_from_form or not canal_id_from_form or not sucursal_id_from_form:
            messages.error(request, "Debe seleccionar un cliente, un canal y una sucursal.")

            return render(request, 'core/pedidos/formulario_pedido.html', context_para_get(request))


        if not (articulo_pks_from_form and 
                len(articulo_pks_from_form) == len(cantidades_from_form) == len(precios_unitarios_from_form)):
            messages.error(request, "Inconsistencia en los datos de los artículos. Intente de nuevo.")

            return render(request, 'core/pedidos/formulario_pedido.html', context_para_get(request))
        
        try:
            cliente = get_object_or_404(Cliente, cliente_id=cliente_id_from_form)
            canal = get_object_or_404(CanalCliente, canal_id=canal_id_from_form)
            sucursal = get_object_or_404(Sucursal, sucursal_id=sucursal_id_from_form)
        except Exception as e:
            messages.error(request, f"Error al obtener cliente, canal o sucursal. Detalle: {e}")

            return render(request, 'core/pedidos/formulario_pedido.html', context_para_get(request))


        with transaction.atomic():
            pedido = Pedido.objects.create(
                cliente=cliente,
                canal=canal,
                sucursal=sucursal,
                fecha=timezone.now().date(),
                subtotal=Decimal('0.00'),
                descuento_total=Decimal('0.00'),
                total_pedido=Decimal('0.00')
            )
            
            subtotal_acumulado_pedido = Decimal('0.00')
            has_valid_items = False

            for pk_str, cantidad_str, precio_str in zip(articulo_pks_from_form, cantidades_from_form, precios_unitarios_from_form):
                if not pk_str or not cantidad_str or not precio_str: 
                    continue
                try:
                    cantidad = int(cantidad_str)
                    precio_unitario_manual = Decimal(precio_str.replace(',', '.')) 

                    if cantidad <= 0 or precio_unitario_manual < Decimal('0.00'):
                        messages.warning(request, f"Cantidad o precio no válidos para un artículo. Fue ignorado.")
                        continue 
                    
                    articulo = get_object_or_404(Articulo, articulo_id=pk_str)
                    has_valid_items = True
                    
                    precio_final_a_usar = precio_unitario_manual
                    subtotal_linea_val = Decimal(cantidad) * precio_final_a_usar
                    subtotal_acumulado_pedido += subtotal_linea_val

                    DetallePedido.objects.create(
                        pedido=pedido,
                        articulo=articulo,
                        cantidad=cantidad,
                        precio_unitario_lista=precio_final_a_usar,
                        subtotal_linea=subtotal_linea_val,
                        total_linea=subtotal_linea_val
                    )
                except Articulo.DoesNotExist:
                    messages.warning(request, f"Artículo con ID {pk_str} no encontrado. Fue ignorado.")
                except (ValueError, InvalidOperation): 
                    messages.warning(request, f"Cantidad '{cantidad_str}' o precio '{precio_str}' no válidos. Fueron ignorados.")
            
            if not has_valid_items:
                messages.error(request, "El pedido no contiene artículos válidos.")
                return redirect('crear_pedido_vista')


            pedido.subtotal = subtotal_acumulado_pedido
            pedido.total_pedido = subtotal_acumulado_pedido
            pedido.save() 

        return procesar_y_aplicar_promociones_a_pedido(request, pedido.pedido_id)

    return render(request, 'core/pedidos/formulario_pedido.html', context_para_get(request))

def context_para_get(request, posted_data=None):
    if posted_data is None:
        posted_data = {}
    return {
        "clientes": Cliente.objects.all().order_by('nombres'),
        "canales": CanalCliente.objects.all().order_by('nombre'),
        "sucursales": Sucursal.objects.all().order_by('nombre'),
        "articulos": Articulo.objects.all().order_by('descripcion'), 
        "posted_cliente_id": posted_data.get("cliente"),
        "posted_canal_id": posted_data.get("canal_cliente"),
        "posted_sucursal_id": posted_data.get("sucursal"),
    }


@login_required
def vista_detalle_pedido(request, pedido_id): 
    pedido = get_object_or_404(Pedido, pedido_id=pedido_id)
    detalles = pedido.detalles.all().order_by('es_bonificacion', 'articulo__descripcion')
    promociones_aplicadas_al_pedido = pedido.promociones_aplicadas.all()
    context = {
        'pedido': pedido,
        'detalles': detalles,
        'promociones_aplicadas_al_pedido': promociones_aplicadas_al_pedido
    }
    return render(request, 'core/pedidos/detalle_pedido.html', context)


# === VISTAS DE BÚSQUEDA PARA AUTOCOMPLETAR (AJAX) ===

@login_required
def buscar_articulos_json(request):
    term = request.GET.get('term', '').strip()
    articulos_qs = Articulo.objects.select_related('empresa')

    if term:
        articulos_qs = articulos_qs.filter(
            Q(codigo_articulo__icontains=term) | 
            Q(descripcion__icontains=term) | 
            Q(empresa__nombre__icontains=term)
        )
    
    articulos = articulos_qs.order_by('empresa__nombre', 'descripcion')[:20]

    results = [
        {
            "id": str(a.articulo_id),
            "text": f"E:{a.empresa.empresa_id} | {a.codigo_articulo} - {a.descripcion}",
            "codigo": a.codigo_articulo,
            "descripcion": a.descripcion,
            "empresa_id": str(a.empresa.empresa_id),
            "empresa_nombre": a.empresa.nombre,
            "precio_venta": str(a.precio_venta) if a.precio_venta is not None else ""
        } for a in articulos
    ]
    return JsonResponse(results, safe=False)

@login_required
def gestionar_promocion_completa(request, promocion_id=None):
    if promocion_id:
        promocion = get_object_or_404(Promocion, promocion_id=promocion_id)
        action_text = "Editar"
    else:
        promocion = None
        action_text = "Crear"

    if request.method == 'POST':
        form_promocion = PromocionModelForm(request.POST, instance=promocion, prefix="promo")
        formset_condiciones = CondicionPromocionFormSet(request.POST, instance=promocion, prefix="cond")
        formset_escalas = EscalaPromocionFormSet(request.POST, instance=promocion, prefix="escala")
        formset_beneficios_directos = BeneficioDirectoPromocionFormSet(request.POST, instance=promocion, prefix="benef_directo")

        are_all_valid = (
            form_promocion.is_valid() and
            formset_condiciones.is_valid() and
            formset_escalas.is_valid() and 
            formset_beneficios_directos.is_valid()
        )

        if are_all_valid:
            try:
                with transaction.atomic():
                    nueva_promocion = form_promocion.save()

                    formset_condiciones.instance = nueva_promocion
                    formset_condiciones.save()
                    
                    if nueva_promocion.es_escalonada:
                        formset_escalas.instance = nueva_promocion
                        formset_escalas.save()
                        
                        if promocion and not promocion.es_escalonada: 
                            BeneficioPromocion.objects.filter(promocion=nueva_promocion, escala__isnull=True).delete()
                    else: 
                        formset_beneficios_directos.instance = nueva_promocion
                        formset_beneficios_directos.save()
                        if promocion and promocion.es_escalonada: 
                            EscalaPromocion.objects.filter(promocion=nueva_promocion).delete()
                    
                    messages.success(request, f"Promoción '{nueva_promocion.nombre}' {action_text.lower()}da correctamente.")
                    return redirect('detalle_promocion', promocion_id=nueva_promocion.promocion_id)
            except Exception as e:
                messages.error(request, f"Ocurrió un error al guardar: {e}")
                print(f"Error en transacción de guardar promoción: {e}")
        else:
            messages.error(request, "Por favor corrija los errores en el formulario.")

    else: # GET
        form_promocion = PromocionModelForm(instance=promocion, prefix="promo")
        formset_condiciones = CondicionPromocionFormSet(instance=promocion, prefix="cond")
        formset_escalas = EscalaPromocionFormSet(instance=promocion, prefix="escala")
        formset_beneficios_directos = BeneficioDirectoPromocionFormSet(instance=promocion, prefix="benef_directo")

    context = {
        'form_promocion': form_promocion,
        'formset_condiciones': formset_condiciones,
        'formset_escalas': formset_escalas,
        'formset_beneficios_directos': formset_beneficios_directos,
        'promocion': promocion,
        'action_text': action_text
    }
    return render(request, 'core/promociones/gestionar_promocion_completa.html', context)

@login_required
def buscar_lineas_json(request):
    term = request.GET.get('term', '').strip()
    lineas_qs = Linea.objects
    if term:
        lineas_qs = lineas_qs.filter(nombre__icontains=term)
    
    lineas = lineas_qs.order_by('nombre')[:20]
    results = [
        {"id": str(l.linea_id), "text": l.nombre} 
        for l in lineas
    ]
    return JsonResponse(results, safe=False)

@login_required
def buscar_grupos_json(request):
    term = request.GET.get('term', '').strip()
    grupos_qs = GrupoProveedor.objects
    if term:
        grupos_qs = grupos_qs.filter(nombre__icontains=term)
        
    grupos = grupos_qs.order_by('nombre')[:20]
    results = [
        {"id": str(g.grupo_id), "text": g.nombre}
        for g in grupos
    ]
    return JsonResponse(results, safe=False)

@login_required
def gestionar_beneficios_de_escala(request, escala_id):
    escala = get_object_or_404(EscalaPromocion, escalapromocion_id=escala_id)
    
    if request.method == 'POST':
        formset = BeneficioEscalaPromocionFormSet(request.POST, instance=escala, prefix='beneficios_escala')
        if formset.is_valid():
            formset.save()
            messages.success(request, f"Beneficios para la escala '{escala.descripcion_escala or escala.pk}' actualizados.")
            return redirect('detalle_promocion', promocion_id=escala.promocion.promocion_id)
        else:
            messages.error(request, "Por favor corrija los errores en los beneficios.")
    else:
        formset = BeneficioEscalaPromocionFormSet(instance=escala, prefix='beneficios_escala')

    context = {
        'escala': escala,
        'promocion': escala.promocion,
        'formset_beneficios_escala': formset,
        'action_text': f"Gestionar Beneficios para Escala: {escala.descripcion_escala or escala.pk}"
    }
    return render(request, 'core/promociones/gestionar_beneficios_escala.html', context)