from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Q, Sum, F, ExpressionWrapper, DecimalField, Count, Min, Max
from django.db import transaction # Para atomicidad en la aplicación de promociones


from .models import (
    Empresa, Sucursal, CanalCliente, GrupoProveedor, Linea, Articulo, Vendedor,
    Cliente, Promocion, CondicionPromocion, EscalaPromocion, BeneficioPromocion,
    Pedido, DetallePedido, PromocionAplicada
)
# Asumo que tienes forms.py con los ModelForms necesarios
from .forms import (
    PromocionModelForm, CondicionPromocionFormSet, EscalaPromocionFormSet, BeneficioDirectoPromocionFormSet, BeneficioEscalaPromocionFormSet
)

from .forms import PromocionModelForm, CondicionPromocionFormSet, EscalaPromocionFormSet, BeneficioDirectoPromocionFormSet


# === UTILIDADES ===
def get_active_promotions_for_pedido(pedido):
    # Asegurarse que pedido.fecha sea un objeto date
    now_date = pedido.fecha
    if hasattr(pedido.fecha, 'date') and callable(pedido.fecha.date): # Si es datetime, convertir a date
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
    empresa_filters = Q() # Filtro vacío por defecto
    if hasattr(pedido.sucursal, 'empresa') and pedido.sucursal.empresa:
        empresa_filters = Q(empresa=pedido.sucursal.empresa)
        print(f"  Paso 2 - Filtro Empresa: {pedido.sucursal.empresa.nombre} (ID: {pedido.sucursal.empresa.empresa_id})")
    else:
        print("  Paso 2 - ADVERTENCIA: Pedido.sucursal no tiene empresa. No se puede filtrar por empresa principal.")
        return Promocion.objects.none() # No continuar si no se puede determinar la empresa

    promociones_paso_2 = promociones_paso_1.filter(empresa_filters)
    print(f"  Paso 2 (después de filtro empresa): {promociones_paso_2.count()} promociones. Nombres: {[p.nombre for p in promociones_paso_2]}")
    if not promociones_paso_2.exists():
        return Promocion.objects.none()

    # 3. Filtro por Sucursal (de la promoción)
    # Una promoción puede aplicar a una sucursal específica o a todas (sucursal=None en la promo)
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
    else: # Si el pedido no tiene canal, solo aplican promos sin canal específico
        canal_filters = Q(canal_cliente_aplicable__isnull=True)
        print("  Paso 4 - Pedido sin canal, filtrando promociones sin canal específico.")
    
    promociones_paso_4 = promociones_paso_3.filter(canal_filters)
    print(f"  Paso 4 (después de filtro canal): {promociones_paso_4.count()} promociones. Nombres: {[p.nombre for p in promociones_paso_4]}")
    if not promociones_paso_4.exists():
        return Promocion.objects.none()

    # 5. Filtro por Tipo de Cliente (del pedido)
    tipo_cliente_filters_applied = Q() # Usaremos este para construir el filtro final
    
    cliente_tipo_actual = None
    if hasattr(pedido.cliente, 'tipo_cliente') and pedido.cliente.tipo_cliente:
        cliente_tipo_actual = pedido.cliente.tipo_cliente.lower() # Convertir a minúsculas para consistencia
        print(f"  Paso 5 - Tipo de Cliente del Pedido (normalizado): '{cliente_tipo_actual}'")

        if cliente_tipo_actual == 'todos':
            # Si el cliente es 'todos', solo le aplican promociones 'todos'.
            tipo_cliente_filters_applied = Q(tipo_cliente='todos')
            print(f"    Cliente es tipo 'todos', buscando SOLO promociones para 'todos'. Filtro Q: {tipo_cliente_filters_applied}")
        else:
            # Si el cliente tiene un tipo específico (ej. 'mayorista'),
            # la promo debe ser para ESE tipo O para 'todos'.
            tipo_cliente_filters_applied = Q(tipo_cliente=cliente_tipo_actual) | Q(tipo_cliente='todos')
            print(f"    Buscando promociones para tipo '{cliente_tipo_actual}' o 'todos'. Filtro Q: {tipo_cliente_filters_applied}")
    else:
        # Si el cliente no tiene tipo_cliente o es un string vacío.
        # Esto es un estado de datos anómalo. Por seguridad, podríamos no aplicar ninguna promo de tipo,
        # o solo las 'todos'. Para ser conservadores, no apliquemos ninguna si el tipo de cliente es inválido.
        print(f"  Paso 5 - ADVERTENCIA: Cliente no tiene tipo_cliente definido o es vacío. No se aplicarán promociones basadas en tipo de cliente específico (excepto 'todos' si se decide).")
        # Si quieres que en este caso solo apliquen promos 'todos':
        tipo_cliente_filters_applied = Q(tipo_cliente='todos')
        # Si quieres que no aplique ninguna promo si el cliente no tiene tipo:
        # print("    Devolviendo QuerySet vacío porque el cliente no tiene tipo.")
        # return Promocion.objects.none()

    # Antes de filtrar, veamos las promociones que llegaron hasta aquí y sus tipos de cliente
    print(f"    Promociones ANTES del filtro de tipo cliente ({promociones_paso_4.count()}):")
    for p_temp in promociones_paso_4:
        print(f"      - Promo: '{p_temp.nombre}', Tipo Cliente Promo: '{p_temp.tipo_cliente}'")

    promociones_finales = promociones_paso_4.filter(tipo_cliente_filters_applied).order_by('prioridad', 'nombre')
    print(f"  Paso 5 (después de filtro tipo cliente): {promociones_finales.count()} promociones. Nombres: {[p.nombre for p in promociones_finales]}")
    # ... (el resto de la función, return promociones_finales) ...
    print(f"--- Fin get_active_promotions_for_pedido ---")
    return promociones_finales


def calculate_condition_totals(pedido_detalles, promocion):
    """
    Calcula la cantidad total y el monto total de los productos en un pedido
    que cumplen con las condiciones de una promoción.
    """
    monto_total_condicion = Decimal('0.00')
    cantidad_total_condicion = 0
    items_que_cumplen_condicion = [] # Guardamos los items para posible descuento sobre ellos

    # Obtener todos los items del pedido que podrían aplicar a alguna condición de la promo
    condiciones_promo = promocion.condiciones.all()
    if not condiciones_promo.exists() and promocion.aplica_por == 'productos_condicion':
        return Decimal('0.00'), 0, [] # No hay condiciones para productos_condicion, no aplica

    # Si aplica_por es total_pedido, se evalúa el total del pedido directamente
    if promocion.aplica_por == 'total_pedido':
        monto_total_condicion = sum(d.subtotal_linea for d in pedido_detalles if not d.es_bonificacion)
        cantidad_total_condicion = sum(d.cantidad for d in pedido_detalles if not d.es_bonificacion)
        items_que_cumplen_condicion = [d for d in pedido_detalles if not d.es_bonificacion]
        return monto_total_condicion, cantidad_total_condicion, items_que_cumplen_condicion

    # Para productos_condicion o conjunto_obligatorio
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
        
        # Si la promoción no especifica artículos/líneas/grupos (condiciones vacías)
        # y aplica_por es 'productos_condicion', se considera que todos los productos aplican.
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
        return True # No es de este tipo, no aplica la restricción

    condiciones_obligatorias = promocion.condiciones.filter(obligatoria_en_conjunto=True)
    if not condiciones_obligatorias.exists():
         # Si es conjunto_obligatorio pero no tiene condiciones marcadas, es un error de configuración.
         # O, si se permite, significa que no hay nada que obligar. Asumamos error config por ahora.
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
                    return False # No cumple la cantidad mínima para este item del conjunto
                encontrado_en_pedido = True
                break # Pasa al siguiente item obligatorio de la condición
        
        if not encontrado_en_pedido:
            return False # Faltó un item obligatorio del conjunto
            
    return True # Todas las condiciones obligatorias del conjunto se cumplieron


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
        # Si no hay precios, subtotal_linea y total_linea ya son 0 y se mantienen así.
        # Si hubiera precios, se recalcularía total_linea: detalle.total_linea = detalle.subtotal_linea
        detalle.save() # Guardar el reseteo del descuento
    
    pedido.descuento_total = Decimal('0.00')
    # No guardar pedido aquí, se guardará al final con todos los totales actualizados.

    # 2. Obtener detalles activos (no bonificaciones) del pedido para evaluación
    # Es importante recargar desde la BD por si el save() anterior no se hizo o para asegurar datos frescos.
    pedido_detalles_activos = list(pedido.detalles.filter(es_bonificacion=False))
    if not pedido_detalles_activos:
        print("No hay detalles activos en el pedido para aplicar promociones.")
        messages.info(request, "El pedido está vacío, no se aplicaron nuevas promociones.")
        # Asegurar que los totales del pedido reflejen esto (probablemente 0)
        pedido.subtotal = sum(d.subtotal_linea for d in pedido.detalles.filter(es_bonificacion=False))
        pedido.total_pedido = pedido.subtotal - pedido.descuento_total # descuento_total es 0
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
        
        beneficios_a_aplicar_config = [] # Lista de (beneficio_model_obj, multiplicador_calculado)
        escala_que_aplico = None

        if promo.es_escalonada:
            print("  La promoción ES ESCALONADA.")
            escalas_promo = promo.escalas.order_by('-desde_cantidad', '-desde_monto') # De mayor a menor para tomar la mejor aplicable
            for escala in escalas_promo:
                print(f"    Evaluando Escala: '{escala.descripcion_escala}' (DesdeCant: {escala.desde_cantidad}, HastaCant: {escala.hasta_cantidad}, DesdeMonto: {escala.desde_monto}, HastaMonto: {escala.hasta_monto})")
                cumple_esta_escala = False
                # Priorizar cantidad si ambos (desde_cantidad y desde_monto) están definidos en la escala
                if escala.desde_cantidad is not None:
                    if cantidad_condicion >= escala.desde_cantidad and (escala.hasta_cantidad is None or cantidad_condicion <= escala.hasta_cantidad):
                        cumple_esta_escala = True
                elif escala.desde_monto is not None: # Solo si no hay desde_cantidad o no cumplió por cantidad
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
                            # No romper, podría haber otra escala menor que no sea proporcional y sí aplique.
                            # O si la política es que si una escala proporcional no da multiplicador > 0, no aplica nada de esa escala:
                            # beneficios_a_aplicar_config = [] # Limpiar
                            # break # Salir del bucle de escalas
                            continue # Intentar con la siguiente escala (si la política es buscar la mejor)


                    print(f"      Multiplicador para beneficios de esta escala: {multiplicador_benef_escala}")
                    for beneficio_obj in escala.beneficios.all():
                        beneficios_a_aplicar_config.append((beneficio_obj, multiplicador_benef_escala))
                    break # Asumimos que solo aplica una escala (la primera que cumpla, por el order_by)
        
        else: # Promoción no escalonada
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

            else: # No es proporcional directa, verificar umbrales fijos de CondicionPromocion
                if promo.aplica_por == 'productos_condicion':
                    cond_directa = promo.condiciones.first() # Asume una condición para el umbral o la primera
                    if cond_directa:
                        print(f"    No proporcional. Evaluando umbrales de CondicionPromocion ID {cond_directa.condicionpromocion_id}: CantMin={cond_directa.cantidad_minima}, MontoMin={cond_directa.monto_minimo}")
                        if (cond_directa.cantidad_minima is None or cantidad_condicion >= cond_directa.cantidad_minima) and \
                           (cond_directa.monto_minimo is None or monto_condicion >= cond_directa.monto_minimo):
                            aplica_promo_no_escalonada_base = True
                    # Si no hay cond_directa pero es 'productos_condicion', ¿debería aplicar si hay cantidad_condicion > 0?
                    # Esto se manejó en calculate_condition_totals (si no hay condiciones, suma todo).
                    # Aquí, si no hay cond_directa, la lógica es que no hay umbral que verificar,
                    # así que si `cantidad_condicion` > 0, podría aplicar.
                    elif not cond_directa and (cantidad_condicion > 0 or monto_condicion > Decimal('0.00')):
                        print(f"    No proporcional, sin condición específica, pero hay items en condición. Aplicando.")
                        aplica_promo_no_escalonada_base = True
                
                elif promo.aplica_por == 'total_pedido' or promo.aplica_por == 'conjunto_obligatorio':
                    # Si es 'total_pedido' o 'conjunto_obligatorio', y llegó hasta aquí,
                    # se asume que las condiciones base (como la existencia del conjunto) ya se cumplieron.
                    # Si se necesitaran umbrales explícitos para 'total_pedido', deberían estar en el modelo Promocion.
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
                # El multiplicador usualmente no afecta el % de descuento, sino la cantidad de veces que se da una bonificación.
                # Si un descuento se aplica "por cada X", la estructura del beneficio debería ser diferente.
                # Aquí asumimos que el % de descuento se aplica una vez si la condición/escala se cumple.
                
                items_sobre_los_que_aplicar_descuento = items_condicion # Por defecto
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
                escala_aplicada=escala_que_aplico, # Será None si no es escalonada o no aplicó escala
                descripcion_beneficios_obtenidos=", ".join(descripcion_beneficios_str_list_para_esta_promo),
                monto_descuento_generado=monto_descuento_generado_por_esta_promo
            )
            promociones_efectivamente_aplicadas_objs.append(promo_aplicada_obj) # Guardar el obj PromocionAplicada
            pedido.descuento_total += monto_descuento_generado_por_esta_promo
            print(f"  PROMOCIÓN '{promo.nombre}' APLICADA. Beneficios: {', '.join(descripcion_beneficios_str_list_para_esta_promo)}. Descuento total de esta promo: {monto_descuento_generado_por_esta_promo}")
        else:
            print(f"  No se generaron beneficios concretos (descripción vacía) para la promoción '{promo.nombre}' aunque cumplió condiciones iniciales.")

    # 4. Recalcular totales finales del pedido y guardar
    # Es importante recargar los detalles por si se añadieron bonificaciones
    detalles_finales_del_pedido_con_bonificaciones = pedido.detalles.all()
    pedido.subtotal = sum(d.subtotal_linea for d in detalles_finales_del_pedido_con_bonificaciones if not d.es_bonificacion)
    # pedido.descuento_total ya fue acumulado a medida que se aplicaban descuentos
    pedido.total_pedido = pedido.subtotal - pedido.descuento_total
    pedido.save() # Guardar el pedido con los totales finales
    print(f"Pedido FINAL guardado: ID={pedido.pedido_id}, Subtotal={pedido.subtotal}, DescuentoTotal={pedido.descuento_total}, TotalPedido={pedido.total_pedido}")

    if promociones_efectivamente_aplicadas_objs:
        messages.success(request, f"Se aplicaron {len(promociones_efectivamente_aplicadas_objs)} promoción(es) al pedido.")
    else:
        messages.info(request, "Ninguna promoción fue aplicable a este pedido o no generaron beneficios concretos.")
    
    print(f"--- FIN PROCESAMIENTO PROMOCIONES PARA PEDIDO: {pedido.pedido_id} ---")
    return redirect('vista_detalle_pedido', pedido_id=pedido.pedido_id)


# === PÁGINA PRINCIPAL ===
def home(request):
    return render(request, 'core/home.html') # Asegúrate que esta plantilla exista

# === AUTENTICACIÓN === (Sin cambios mayores, parecen funcionales)
def login_user(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, "Sesión iniciada correctamente.")
            # Redirigir a una página relevante, ej. listar pedidos o crear promo
            return redirect('listar_promociones')
        else:
            messages.error(request, "Nombre de usuario o contraseña incorrectos.")
            return redirect('login_user') # Redirigir de nuevo a la página de login
    return render(request, 'core/login/login.html') # Asegúrate que esta plantilla exista

def logout_user(request):
    logout(request)
    messages.success(request, "Sesión cerrada correctamente.")
    return redirect('home')

# === CRUD PROMOCIONES ===
# Para un CRUD completo y amigable de Promociones con sus condiciones, escalas y beneficios anidados,
# se recomienda usar ModelForms y Django's inlineformset_factory.
# Las vistas aquí serán simplificadas o necesitarán desarrollo adicional para los formsets.

@login_required
def listar_promociones(request):
    promociones = Promocion.objects.all().order_by('-activa', 'prioridad', 'nombre')
    return render(request, 'core/promociones/listar_promociones.html', {'promociones': promociones})

@login_required
def crear_promocion(request):
    # Esta vista necesitaría manejar FormSets para Condicion, Escala, Beneficio.
    # Por simplicidad, solo se muestra el form de Promocion.
    if request.method == 'POST':
        form = PromocionModelForm(request.POST) # <--- CORREGIDO
        if form.is_valid():
            promocion = form.save()
            messages.success(request, f"Promoción '{promocion.nombre}' creada. Agregue condiciones, escalas y beneficios.")
            return redirect('detalle_promocion', promocion_id=promocion.promocion_id)
        else:
            messages.error(request, "Por favor corrija los errores en el formulario.")
    else:
        form = PromocionModelForm() # <--- CORREGIDO
    return render(request, 'core/promociones/formulario_promocion.html', {'form': form, 'action': 'Crear'})

@login_required
def editar_promocion(request, promocion_id):
    promocion = get_object_or_404(Promocion, promocion_id=promocion_id)
    if request.method == 'POST':
        form = PromocionModelForm(request.POST, instance=promocion) # <--- CORREGIDO
        if form.is_valid():
            form.save()
            messages.success(request, f"Promoción '{promocion.nombre}' actualizada.")
            return redirect('detalle_promocion', promocion_id=promocion.promocion_id)
        else:
            messages.error(request, "Por favor corrija los errores en el formulario.")
    else:
        form = PromocionModelForm(instance=promocion) # <--- CORREGIDO
    return render(request, 'core/promociones/formulario_promocion.html', {'form': form, 'promocion': promocion, 'action': 'Editar'})

@login_required
def detalle_promocion(request, promocion_id):
    promocion = get_object_or_404(Promocion, promocion_id=promocion_id)
    # Aquí podrías mostrar forms para añadir/editar condiciones, escalas, beneficios
    # usando inlineformset_factory o vistas separadas.
    condiciones = promocion.condiciones.all()
    escalas = promocion.escalas.all() # Cada escala tendrá sus beneficios
    beneficios_directos = promocion.beneficios_directos.all() # Para promos no escalonadas

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

        # Validar todos los formularios y formsets
        are_all_valid = (
            form_promocion.is_valid() and
            formset_condiciones.is_valid() and
            formset_escalas.is_valid() and
            formset_beneficios_directos.is_valid()
        )

        if are_all_valid:
            try:
                with transaction.atomic():
                    # Guardar la promoción principal
                    nueva_promocion = form_promocion.save()

                    # Guardar condiciones
                    formset_condiciones.instance = nueva_promocion
                    formset_condiciones.save() # Esto guarda las condiciones

                    # Guardar beneficios directos (si la promo no es escalonada)
                    if not nueva_promocion.es_escalonada:
                        formset_beneficios_directos.instance = nueva_promocion
                        formset_beneficios_directos.save()
                    else: # Si es escalonada, borrar beneficios directos por si acaso
                        if promocion: # Si estamos editando una promoción existente
                            BeneficioPromocion.objects.filter(promocion=promocion, escala__isnull=True).delete()


                    # Guardar escalas y SUS beneficios "aplanados"
                    if nueva_promocion.es_escalonada:
                        formset_escalas.instance = nueva_promocion
                        
                        # Guardar las instancias de EscalaPromocion
                        # El save() del formset llamará al save() de cada EscalaPromocionModelForm.
                        # Dentro del save() de EscalaPromocionModelForm NO debemos llamar a save_beneficios().
                        # Lo haremos explícitamente después.
                        
                        # Guardar instancias de EscalaPromocion.
                        # No podemos llamar a form_escala.save_beneficios() dentro del save() del form
                        # si la escala es nueva y aún no tiene PK.
                        
                        # Paso 1: Guardar las escalas (crea/actualiza EscalaPromocion)
                        # commit=True es necesario aquí para que las instancias de escala tengan PK
                        # antes de que intentemos guardar sus beneficios.
                        escalas_instances = formset_escalas.save(commit=True) # Esto guarda las escalas

                        # Paso 2: Iterar sobre los formularios del formset (que ahora tienen instancias)
                        # y llamar al método personalizado para guardar los beneficios.
                        for form_escala in formset_escalas.forms:
                            if form_escala.is_valid() and form_escala.has_changed(): # Solo si es válido y tiene cambios
                                if form_escala.cleaned_data.get('DELETE', False):
                                    # El formset.save() ya debería haber manejado la eliminación de la escala
                                    # y CASCADE debería eliminar sus beneficios.
                                    # Si no, necesitarías: if form_escala.instance.pk: form_escala.instance.delete()
                                    pass
                                else:
                                    # form_escala.instance ya es la instancia de EscalaPromocion guardada.
                                    if form_escala.instance.pk: # Asegurarse que la escala tiene PK
                                        form_escala.save_beneficios(escala_instance=form_escala.instance)
                    else: # Si no es escalonada, borrar escalas existentes por si acaso
                        if promocion: # Si estamos editando
                             EscalaPromocion.objects.filter(promocion=promocion).delete()


                    messages.success(request, f"Promoción '{nueva_promocion.nombre}' {action_text.lower()}da correctamente.")
                    return redirect('detalle_promocion', promocion_id=nueva_promocion.promocion_id)
            except Exception as e:
                messages.error(request, f"Ocurrió un error al guardar: {e}")
                # Aquí es bueno imprimir el error en la consola del servidor para depuración
                print(f"Error en transacción de guardar promoción: {e}")


        else: # Si algún formulario o formset no es válido
            messages.error(request, "Por favor corrija los errores en el formulario.")
            # Debugging de errores
            print("Errores form_promocion:", form_promocion.errors, form_promocion.non_field_errors())
            print("Errores formset_condiciones:", formset_condiciones.errors, formset_condiciones.non_form_errors())
            print("Errores formset_escalas:", formset_escalas.errors, formset_escalas.non_form_errors())
            for i, form_err in enumerate(formset_escalas.errors):
                if form_err: print(f"  Errores en Escala form {i}: {form_err}")
            print("Errores formset_beneficios_directos:", formset_beneficios_directos.errors, formset_beneficios_directos.non_form_errors())

    else: # GET request
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


# === VISTAS PARA CREAR/GESTIONAR CONDICIONES, ESCALAS, BENEFICIOS (Simplificado) ===
# Estas vistas necesitarían formularios adecuados (ModelForms) y lógica para asociarlos
# correctamente a la Promoción o EscalaPromocion.

# Ejemplo para Condiciones (requiere CondicionPromocionForm en forms.py)
@login_required
def gestionar_condiciones_promocion(request, promocion_id):
    promocion = get_object_or_404(Promocion, promocion_id=promocion_id)
    CondicionFormSet = CondicionPromocionFormSet # Asume que tienes este formset
    
    if request.method == 'POST':
        formset = CondicionFormSet(request.POST, instance=promocion)
        if formset.is_valid():
            formset.save()
            messages.success(request, "Condiciones actualizadas.")
            return redirect('detalle_promocion', promocion_id=promocion.promocion_id)
    else:
        formset = CondicionFormSet(instance=promocion)
        
    return render(request, 'core/promociones/gestionar_condiciones.html', {'promocion': promocion, 'formset': formset})

# De manera similar se crearían vistas para gestionar_escalas_promocion y gestionar_beneficios_promocion/escala

# === CRUD PEDIDOS ===
@login_required
def listar_pedidos(request):
    pedidos = Pedido.objects.all().order_by('-fecha')
    return render(request, 'core/pedidos/listar_pedidos.html', {'pedidos': pedidos})

@login_required
def crear_pedido_vista(request):
    if request.method == "POST":
        cliente_id_from_form = request.POST.get("cliente")
        # El name del select en tu HTML es 'canal_cliente'
        canal_id_from_form = request.POST.get("canal_cliente")
        # El name del select en tu HTML es 'sucursal'
        sucursal_id_from_form = request.POST.get("sucursal")
        
        articulo_pks_from_form = request.POST.getlist("articulo_pk[]")
        cantidades_from_form = request.POST.getlist("cantidad[]")

        # --- Validación de Cabecera del Pedido ---
        if not cliente_id_from_form or not canal_id_from_form or not sucursal_id_from_form:
            messages.error(request, "Debe seleccionar un cliente, un canal y una sucursal.")
            # Recargar el formulario para que el usuario no pierda datos
            # (Este contexto es el mismo que para el GET)
            context = {
                "clientes": Cliente.objects.all().order_by('nombres'),
                "canales": CanalCliente.objects.all().order_by('nombre'),
                "sucursales": Sucursal.objects.all().order_by('nombre'),
                "articulos": Articulo.objects.all().order_by('descripcion'),
                "posted_cliente_id": cliente_id_from_form,
                "posted_canal_id": canal_id_from_form,
                "posted_sucursal_id": sucursal_id_from_form,
                # Aquí podrías incluso pasar los artículos y cantidades para repopular el JS si es complejo
            }
            return render(request, 'core/pedidos/formulario_pedido.html', context)

        try:
            # Usar los nombres de campo PK correctos de tus modelos
            cliente = get_object_or_404(Cliente, cliente_id=cliente_id_from_form)
            canal = get_object_or_404(CanalCliente, canal_id=canal_id_from_form) # canal_id es CharField PK
            sucursal = get_object_or_404(Sucursal, sucursal_id=sucursal_id_from_form) # sucursal_id es CharField PK
        except Exception as e: # Captura más genérica para debug
            messages.error(request, f"Error al obtener cliente, canal o sucursal. Detalle: {e}")
            context = { # Repetir contexto para recargar el form
                "clientes": Cliente.objects.all().order_by('nombres'),
                "canales": CanalCliente.objects.all().order_by('nombre'),
                "sucursales": Sucursal.objects.all().order_by('nombre'),
                "articulos": Articulo.objects.select_related('empresa').all().order_by('descripcion', 'empresa_id'),
                "posted_cliente_id": cliente_id_from_form,
                "posted_canal_id": canal_id_from_form,
                "posted_sucursal_id": sucursal_id_from_form,
            }
            return render(request, 'core/pedidos/formulario_pedido.html', context)

        # --- Validación de Artículos del Pedido ---
        if not articulo_pks_from_form or not any(articulo_pks_from_form) or len(articulo_pks_from_form) != len(cantidades_from_form):
            messages.error(request, "Debe agregar al menos un artículo con su cantidad al pedido.")
            # (Recargar form con contexto como arriba)
            context = {
                "clientes": Cliente.objects.all().order_by('nombres'),
                "canales": CanalCliente.objects.all().order_by('nombre'),
                "sucursales": Sucursal.objects.all().order_by('nombre'),
                "articulos": Articulo.objects.all().order_by('descripcion'),
                "posted_cliente_id": cliente_id_from_form,
                "posted_canal_id": canal_id_from_form,
                "posted_sucursal_id": sucursal_id_from_form,
            }
            return render(request, 'core/pedidos/formulario_pedido.html', context)
        
        # Validar que los artículos seleccionados no estén vacíos y las cantidades sean positivas
        items_validos_en_post = False
        for pk_str, cant_str in zip(articulo_pks_from_form, cantidades_from_form):
            if pk_str and cant_str: # Asegurarse que ambos tienen valor
                try:
                    if int(cant_str) > 0:
                        items_validos_en_post = True
                        break
                except ValueError:
                    pass # Ignorar si la cantidad no es un número para esta validación
        
        if not items_validos_en_post:
            messages.error(request, "Debe seleccionar al menos un artículo y especificar una cantidad positiva.")
            # (Recargar form con contexto como arriba)
            context = {
                "clientes": Cliente.objects.all().order_by('nombres'),
                "canales": CanalCliente.objects.all().order_by('nombre'),
                "sucursales": Sucursal.objects.all().order_by('nombre'),
                "articulos": Articulo.objects.all().order_by('descripcion'),
                "posted_cliente_id": cliente_id_from_form,
                "posted_canal_id": canal_id_from_form,
                "posted_sucursal_id": sucursal_id_from_form,
            }
            return render(request, 'core/pedidos/formulario_pedido.html', context)


        with transaction.atomic():
            pedido = Pedido.objects.create(
                cliente=cliente,
                canal=canal,
                sucursal=sucursal,
                fecha=timezone.now().date(), # O timezone.now() para DateTime
                # Los montos se inicializan en 0 y se calcularán después
                subtotal=Decimal('0.00'),
                descuento_total=Decimal('0.00'),
                total_pedido=Decimal('0.00')
            )
            
            # No necesitamos subtotal_acumulado_pedido aquí si no hay precios

            for pk_str, cantidad_str in zip(articulo_pks_from_form, cantidades_from_form):
                # Omitir si el artículo no fue seleccionado o la cantidad está vacía/no es válida
                if not pk_str or not cantidad_str:
                    continue
                try:
                    cantidad = int(cantidad_str)
                    if cantidad <= 0:
                        continue # Ignorar cantidades no positivas
                    
                    # Usar el nombre del PK correcto de Articulo
                    articulo = get_object_or_404(Articulo, articulo_id=pk_str)
                    
                    # Como no hay precios en Articulo, los montos de línea son 0.
                    precio_unitario_val = Decimal('0.00')
                    subtotal_linea_val = Decimal('0.00') # cantidad * precio_unitario_val

                    DetallePedido.objects.create(
                        pedido=pedido,
                        articulo=articulo,
                        cantidad=cantidad,
                        precio_unitario_lista=precio_unitario_val,
                        subtotal_linea=subtotal_linea_val,
                        total_linea=subtotal_linea_val # Inicialmente sin descuento
                    )
                except Articulo.DoesNotExist:
                    messages.warning(request, f"Artículo con ID {pk_str} no encontrado. Fue ignorado.")
                    continue
                except ValueError:
                    messages.warning(request, f"Cantidad '{cantidad_str}' no es un número válido para el artículo con ID {pk_str}. Fue ignorado.")
                    continue
            
            # El pedido.subtotal y pedido.total_pedido serán recalculados y guardados
            # dentro de procesar_y_aplicar_promociones_a_pedido.
            # No es necesario un pedido.save() aquí específicamente para esos campos.

        # Llamar a la función para procesar y aplicar promociones.
        # Esta función debería manejar el redirect final.
        return procesar_y_aplicar_promociones_a_pedido(request, pedido.pedido_id)

    # Contexto para el método GET
    context = {
        "clientes": Cliente.objects.all().order_by('nombres'),
        "canales": CanalCliente.objects.all().order_by('nombre'),
        "sucursales": Sucursal.objects.all().order_by('nombre'),
        "articulos": Articulo.objects.all().order_by('descripcion') # Usando "articulos" como en tu plantilla
    }
    return render(request, 'core/pedidos/formulario_pedido.html', context)


@login_required
def vista_detalle_pedido(request, pedido_id): # Renombrada para claridad
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
# views.py

@login_required
def buscar_articulos_json(request):
    term = request.GET.get('term', '').strip()
    # Filtrar por empresa si es necesario o relevante para la búsqueda.
    # Por ahora, búsqueda general.
    # Considera añadir un filtro por la empresa de la sucursal seleccionada en el pedido si es relevante.
    # sucursal_id = request.GET.get('sucursal_id')
    # if sucursal_id:
    #   try:
    #       sucursal = Sucursal.objects.get(sucursal_id=sucursal_id)
    #       articulos_qs = Articulo.objects.select_related('empresa').filter(empresa=sucursal.empresa)
    #   except Sucursal.DoesNotExist:
    #       articulos_qs = Articulo.objects.select_related('empresa') # Fallback
    # else:
    #   articulos_qs = Articulo.objects.select_related('empresa')

    articulos_qs = Articulo.objects.select_related('empresa') # Siempre hacer select_related

    if term:
        articulos_qs = articulos_qs.filter(
            Q(codigo_articulo__icontains=term) | Q(descripcion__icontains=term) | Q(empresa__nombre__icontains=term)
        )
    
    articulos = articulos_qs.order_by('empresa__nombre', 'descripcion')[:20] # Limitar resultados

    results = [
        {
            "id": str(a.articulo_id), # El ID del artículo para el value
            "text": f"E:{a.empresa.empresa_id} | {a.codigo_articulo} - {a.descripcion}", # Texto a mostrar en el autocompletar
            "codigo": a.codigo_articulo,
            "descripcion": a.descripcion,
            "empresa_id": str(a.empresa.empresa_id), # ID de la empresa
            "empresa_nombre": a.empresa.nombre, # Nombre de la empresa
            # "precio": str(getattr(a, 'precio_venta', '0.00')) # Si tuvieras precio
        } for a in articulos
    ]
    return JsonResponse(results, safe=False)

# ... (mantener buscar_linea, buscar_grupo si aún son necesarias para formularios de Promocion)
# ... (tus vistas de eliminar_condicion, eliminar_beneficio, eliminar_escala pueden mantenerse,
#      asegúrate que redirigen correctamente y usan el promocion_id y no el pk simple si es UUID)

# Las funciones `aplicar_beneficio` y `evaluar_promociones` que tenías antes
# han sido integradas y mejoradas dentro de `procesar_y_aplicar_promociones_a_pedido`.

# La función `aplicar_promociones` original ahora es `procesar_y_aplicar_promociones_a_pedido`
# y toma `request` como primer argumento.

# En tu views.py
# from .forms import PromocionModelForm, CondicionPromocionFormSet, EscalaPromocionFormSet, BeneficioDirectoPromocionFormSet

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

        if (form_promocion.is_valid() and
            formset_condiciones.is_valid() and
            formset_escalas.is_valid() and
            formset_beneficios_directos.is_valid()):

            with transaction.atomic(): # Envolver todo en una transacción
                nueva_promocion = form_promocion.save()
                
                formset_condiciones.instance = nueva_promocion
                formset_condiciones.save()
                
                formset_escalas.instance = nueva_promocion
                # Guardar los formularios de escala. Esto NO guarda los beneficios aún.
                # `forms_saved` contiene las instancias de EscalaPromocion guardadas o actualizadas.
                escalas_guardadas = formset_escalas.save() # save() del formset base

                # Ahora, para cada formulario de escala que fue guardado (o está siendo creado),
                # llama al método save_beneficio que definimos en EscalaPromocionModelForm.
                for form_escala in formset_escalas:
                    if form_escala.is_valid() and form_escala.has_changed(): # Procesar solo si es válido y cambió
                        if form_escala.cleaned_data.get('DELETE'):
                            # Si la escala se marca para eliminar, el formset.save() ya la maneja.
                            # Los beneficios asociados se borrarán por CASCADE si la FK en BeneficioPromocion
                            # tiene on_delete=models.CASCADE hacia EscalaPromocion.
                            pass
                        else:
                            # La instancia de escala ya fue creada/actualizada por formset_escalas.save()
                            # o se creará si es un form nuevo.
                            # Si es un form nuevo, form_escala.instance.pk será None antes de este save.
                            # El save() del ModelForm (EscalaPromocionModelForm) será llamado por el formset.save().
                            # Necesitamos asegurar que la instancia de escala esté guardada ANTES de llamar a save_beneficio.
                            # `form_escala.instance` después de `formset_escalas.save()` debería tener el objeto Escala con su PK.
                            if form_escala.instance.pk: # Solo si la escala se guardó o ya existía
                                form_escala.save_beneficio(escala_instance=form_escala.instance)


                formset_beneficios_directos.instance = nueva_promocion
                formset_beneficios_directos.save()
            
            messages.success(request, f"Promoción '{nueva_promocion.nombre}' {action_text.lower()}da correctamente.")
            return redirect('detalle_promocion', promocion_id=nueva_promocion.promocion_id)
        else:
            messages.error(request, "Por favor corrija los errores en el formulario.")
            # Imprimir errores para depuración
            # print("Errores form_promocion:", form_promocion.errors)
            # print("Errores formset_condiciones:", formset_condiciones.errors)
            # print("Errores formset_condiciones non_form_errors:", formset_condiciones.non_form_errors())
            # print("Errores formset_escalas:", formset_escalas.errors)
            # print("Errores formset_escalas non_form_errors:", formset_escalas.non_form_errors())
            # print("Errores formset_beneficios_directos:", formset_beneficios_directos.errors)
            # print("Errores formset_beneficios_directos non_form_errors:", formset_beneficios_directos.non_form_errors())


    else: # GET request
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
    # Podrías filtrar por empresa si las líneas son específicas de empresa
    # empresa_id = request.GET.get('empresa_id') 
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
    # Podrías filtrar por empresa
    grupos_qs = GrupoProveedor.objects
    if term:
        grupos_qs = grupos_qs.filter(nombre__icontains=term)
        
    grupos = grupos_qs.order_by('nombre')[:20]
    results = [
        {"id": str(g.grupo_id), "text": g.nombre}
        for g in grupos
    ]
    return JsonResponse(results, safe=False)
