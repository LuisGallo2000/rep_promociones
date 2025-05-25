from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from decimal import Decimal
from django.db.models import Q, Sum, F
from django.db.models import ExpressionWrapper, DecimalField

from .models import (
    GrupoProveedor, Linea, Promocion, Pedido, DetallePedido, PromocionAplicada,
    CondicionPromocion, BeneficioPromocion, EscalaPromocion, Articulo, Cliente, CanalCliente, Sucursal
)
from .forms import CondicionPromocionForm, PromocionForm


# === PÁGINA PRINCIPAL ===
def home(request):
    return render(request, 'core/home.html')


# === AUTENTICACIÓN ===
def login_user(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            messages.success(request, "Sesión iniciada correctamente")
            return redirect('crear_promocion')
        else:
            messages.error(request, "Credenciales incorrectas")
            return redirect('login')
    return render(request, 'core/login/login.html')


def logout_user(request):
    logout(request)
    messages.success(request, "Sesión cerrada")
    return redirect('home')


# === CRUD PROMOCIONES ===

@login_required
def listar_promociones(request):
    promociones = Promocion.objects.all()
    promociones = Promocion.objects.all().order_by('-fecha_inicio')
    return render(request, 'core/promociones/listar.html', {'promociones': promociones})


@login_required
def crear_promocion(request):
    if request.method == 'POST':
        form = PromocionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Promoción creada correctamente")
            return redirect('listar_promociones')
    else:
        form = PromocionForm()
    return render(request, 'core/promociones/formulario.html', {'form': form})


@login_required
def editar_promocion(request, pk):
    promocion = get_object_or_404(Promocion, pk=pk)
    if request.method == 'POST':
        form = PromocionForm(request.POST, instance=promocion)
        if form.is_valid():
            form.save()
            messages.success(request, "Promoción actualizada correctamente")
            return redirect('listar_promociones')
    else:
        form = PromocionForm(instance=promocion)
    return render(request, 'core/promociones/formulario.html', {'form': form})


@login_required
def eliminar_promocion(request, pk):
    promocion = get_object_or_404(Promocion, pk=pk)
    if request.method == 'POST':
        promocion.delete()
        messages.success(request, "Promoción eliminada correctamente")
        return redirect('listar_promociones')
    return render(request, 'core/promociones/confirmar_eliminar.html', {'promocion': promocion})



@login_required
def detalle_promocion(request, pk):
    print(f"Entrando a detalle_promocion con pk={pk}")
    promocion = get_object_or_404(Promocion, pk=pk)
    condiciones = CondicionPromocion.objects.filter(promocion=promocion)
    beneficios = BeneficioPromocion.objects.filter(promocion=promocion)
    escalas = EscalaPromocion.objects.filter(promocion=promocion)
    return render(request, 'core/promociones/detalle.html', {
        'promocion': promocion,
        'condiciones': condiciones,
        'beneficios': beneficios,
        'escalas': escalas
    })


# === APLICACIÓN DE PROMOCIONES A PEDIDOS ===

@login_required
def aplicar_promociones(request, pedido_id):
    pedido = get_object_or_404(Pedido, pk=pedido_id)
    detalles = DetallePedido.objects.filter(pedido=pedido)
    promociones = Promocion.objects.filter(
        canal=pedido.canal,
        sucursal=pedido.sucursal,
        tipo_cliente=pedido.cliente.tipo_cliente,
        fecha_inicio__lte=pedido.fecha,
        fecha_fin__gte=pedido.fecha
    )

    total_bonificado = Decimal('0.00')
    total_descuento = Decimal('0.00')

    for promo in promociones:
        condiciones = CondicionPromocion.objects.filter(promocion=promo)
        cumple = False

        for condicion in condiciones:
            detalles_filtrados = detalles

            if condicion.articulo:
                detalles_filtrados = detalles_filtrados.filter(articulo=condicion.articulo)
            elif condicion.linea:
                detalles_filtrados = detalles_filtrados.filter(articulo__linea=condicion.linea)
            elif condicion.grupo:
                detalles_filtrados = detalles_filtrados.filter(articulo__grupo=condicion.grupo)

            total_cantidad = detalles_filtrados.aggregate(total=Sum('cantidad'))['total'] or 0
            
            detalles_filtrados = detalles_filtrados.annotate(
                subtotal=ExpressionWrapper(
                    F('cantidad') * F('precio_unitario'),
                    output_field=DecimalField(max_digits=12, decimal_places=2)
                )
            )
            total_monto = detalles_filtrados.aggregate(total=Sum('subtotal'))['total'] or 0


            if (not condicion.cantidad_minima or total_cantidad >= condicion.cantidad_minima) and \
               (not condicion.monto_minimo or total_monto >= condicion.monto_minimo):
                cumple = True
                break

        if cumple:
            beneficio = BeneficioPromocion.objects.filter(promocion=promo).first()
            if beneficio:
                if beneficio.tipo == 'bonificacion':
                    total_bonificado += Decimal(beneficio.cantidad or 0)
                elif beneficio.tipo == 'descuento':
                    descuento = sum([
                        d.cantidad * d.precio_unitario * (beneficio.porcentaje_descuento / 100)
                        for d in detalles
                    ])
                    total_descuento += Decimal(descuento)

            PromocionAplicada.objects.create(
                pedido=pedido,
                promocion=promo,
                descuento_aplicado=total_descuento,
                total_bonificado=total_bonificado
            )

    messages.success(request, "Promociones aplicadas correctamente")
    return redirect('detalle_pedido', pedido_id=pedido.id)

def buscar_articulo(request):
    term = request.GET.get('term', '')
    articulos = Articulo.objects.filter(nombre__icontains=term)[:10]
    results = [{'id': a.id, 'label': a.nombre, 'value': a.nombre} for a in articulos]
    return JsonResponse(results, safe=False)

def buscar_linea(request):
    term = request.GET.get('term', '')
    lineas = Linea.objects.filter(nombre__icontains=term)[:10]
    results = [{'id': l.id, 'label': l.nombre, 'value': l.nombre} for l in lineas]
    return JsonResponse(results, safe=False)

def buscar_grupo(request):
    term = request.GET.get('term', '')
    grupos = GrupoProveedor.objects.filter(nombre__icontains=term)[:10]
    results = [{'id': g.id, 'label': g.nombre, 'value': g.nombre} for g in grupos]
    return JsonResponse(results, safe=False)

@login_required
def crear_condicion(request, promocion_id):
    promocion = get_object_or_404(Promocion, id=promocion_id)

    if request.method == 'POST':
        form = CondicionPromocionForm(request.POST)
        if form.is_valid():
            condicion = form.save(commit=False)
            condicion.promocion = promocion
            condicion.save()
            messages.success(request, "Condición registrada.")
            return redirect('listar_promociones')
    else:
        form = CondicionPromocionForm()

    return render(request, 'core/condiciones/formulario.html', {'form': form, 'promocion': promocion})

@login_required
def buscar_articulos(request):
    q = request.GET.get('q', '')
    articulos = Articulo.objects.filter(descripcion__icontains=q)[:20]
    data = [{'id': str(a.articulo_id), 'descripcion': a.descripcion} for a in articulos]
    return JsonResponse(data, safe=False)

@login_required
def crear_beneficio(request, promocion_id):
    promocion = get_object_or_404(Promocion, id=promocion_id)
    if request.method == 'POST':
        tipo = request.POST.get('tipo')
        articulo_id = request.POST.get('articulo') or None
        cantidad = request.POST.get('cantidad') or None
        porcentaje_descuento = request.POST.get('porcentaje_descuento') or None

        BeneficioPromocion.objects.create(
            promocion=promocion,
            tipo=tipo,
            articulo_id=articulo_id,
            cantidad=cantidad,
            porcentaje_descuento=porcentaje_descuento
        )
        messages.success(request, "Beneficio registrado.")
        return redirect('detalle_promocion', pk=promocion.id)

    return render(request, 'core/beneficios/formulario.html', {'promocion': promocion})

@login_required
def crear_escala(request, promocion_id, condicion_id):
    promocion = get_object_or_404(Promocion, id=promocion_id)
    condicion = get_object_or_404(CondicionPromocion, id=condicion_id)
    if request.method == 'POST':
        escala = EscalaPromocion(
            promocion=promocion,
            condicion=condicion,
            desde_monto=request.POST.get('desde_monto') or None,
            hasta_monto=request.POST.get('hasta_monto') or None,
            desde_cantidad=request.POST.get('desde_cantidad') or None,
            hasta_cantidad=request.POST.get('hasta_cantidad') or None,
            tipo_beneficio=request.POST.get('tipo_beneficio'),
            articulo_bonificado_id=request.POST.get('articulo_bonificado') or None,
            cantidad_bonificada=request.POST.get('cantidad_bonificada') or None,
            porcentaje_descuento=request.POST.get('porcentaje_descuento') or None,
            proporcional='proporcional' in request.POST
        )
        escala.save()
        messages.success(request, "Escala registrada.")
        return redirect('detalle_promocion', pk=promocion.id)

    return render(request, 'core/escalas/formulario.html', {
        'promocion': promocion,
        'condicion': condicion
    })

@login_required
def promociones_aplicadas(request, pedido_id):
    aplicadas = PromocionAplicada.objects.filter(pedido_id=pedido_id)
    return render(request, 'core/pedidos/promociones_aplicadas.html', {'aplicadas': aplicadas})

@login_required
def gestionar_condiciones(request, pk):
    promocion = get_object_or_404(Promocion, pk=pk)
    condiciones = CondicionPromocion.objects.filter(promocion=promocion)
    return render(request, 'core/condiciones/gestionar.html', {
        'promocion': promocion,
        'condiciones': condiciones
    })

@login_required
def eliminar_condicion(request, pk):
    condicion = get_object_or_404(CondicionPromocion, pk=pk)
    promocion_id = condicion.promocion.id
    if request.method == 'POST':
        condicion.delete()
        messages.success(request, "Condición eliminada correctamente")
        return redirect('gestionar_condiciones', pk=promocion_id)
    return render(request, 'core/condiciones/confirmar_eliminar.html', {'condicion': condicion})

@login_required
def gestionar_beneficios(request, pk):
    promocion = get_object_or_404(Promocion, pk=pk)
    beneficios = BeneficioPromocion.objects.filter(promocion=promocion)
    return render(request, 'core/beneficios/gestionar.html', {
        'promocion': promocion,
        'beneficios': beneficios
    })

@login_required
def eliminar_beneficio(request, pk):
    beneficio = get_object_or_404(BeneficioPromocion, pk=pk)
    promocion_id = beneficio.promocion.id
    if request.method == 'POST':
        beneficio.delete()
        messages.success(request, "Beneficio eliminado correctamente")
        return redirect('gestionar_beneficios', pk=promocion_id)
    return render(request, 'core/beneficios/confirmar_eliminar.html', {'beneficio': beneficio})

@login_required
def gestionar_escalas(request, pk):
    promocion = get_object_or_404(Promocion, pk=pk)
    escalas = EscalaPromocion.objects.filter(promocion=promocion)
    return render(request, 'core/escalas/gestionar.html', {
        'promocion': promocion,
        'escalas': escalas
    })

@login_required
def eliminar_escala(request, pk):
    escala = get_object_or_404(EscalaPromocion, pk=pk)
    promocion_id = escala.promocion.id
    if request.method == 'POST':
        escala.delete()
        messages.success(request, "Escala eliminada correctamente")
        return redirect('gestionar_escalas', pk=promocion_id)
    return render(request, 'core/escalas/confirmar_eliminar.html', {'escala': escala})


def aplicar_beneficio(pedido, promocion):
    beneficio = BeneficioPromocion.objects.filter(promocion=promocion).first()
    if not beneficio:
        return None  # No hay beneficio que aplicar

    if beneficio.tipo_beneficio == 'descuento':
        descuento = sum([
            d.cantidad * d.precio_unitario * (beneficio.porcentaje_descuento / 100)
            for d in pedido.detallepedido_set.all()
        ])
        pedido.total -= descuento
        pedido.save()

    elif beneficio.tipo_beneficio == 'bonificacion':
        # Agrega un producto bonificado (articulo)
        DetallePedido.objects.create(
            pedido=pedido,
            articulo=beneficio.articulo_bonificado,  # Asegúrate de que el modelo tenga este campo
            cantidad=beneficio.cantidad_bonificada,
            precio_unitario=0,
            subtotal=0
        )

    # Registrar promoción aplicada
    PromocionAplicada.objects.create(pedido=pedido, promocion=promocion)


def evaluar_promociones(pedido):
    promociones_aplicables = []

    for promocion in Promocion.objects.filter(estado='activa'):
        condiciones = CondicionPromocion.objects.filter(promocion=promocion)
        cumple_todas = True

        for condicion in condiciones:
            if condicion.tipo_condicion == 'monto':
                if pedido.total < condicion.valor:
                    cumple_todas = False
            elif condicion.tipo_condicion == 'cantidad':
                cantidad_total = sum(d.cantidad for d in pedido.detallepedido_set.all())
                if cantidad_total < condicion.valor:
                    cumple_todas = False
            # Agrega más condiciones si tienes

        if cumple_todas:
            promociones_aplicables.append(promocion)

    return promociones_aplicables


def aplicar_promociones_a_pedido(pedido):
    promociones = evaluar_promociones(pedido)
    for promocion in promociones:
        if not PromocionAplicada.objects.filter(pedido=pedido, promocion=promocion).exists():
            aplicar_beneficio(pedido, promocion)


def crear_pedido(request):
    if request.method == "POST":
        cliente_id = request.POST.get("cliente")
        canal_id = request.POST.get("canal")  # Captura el canal
        sucursal_id = request.POST.get("sucursal")  # Captura la sucursal
        articulo_ids = request.POST.getlist("articulo_id[]")  # Usamos getlist para obtener múltiples artículos
        cantidades = request.POST.getlist("cantidad[]")  # Lo mismo para las cantidades

        if not cliente_id or not articulo_ids or not canal_id or not sucursal_id:
            messages.error(request, "Debe seleccionar un cliente, un canal, una sucursal y al menos un artículo.")
            return redirect("crear_pedido")

        try:
            cliente = Cliente.objects.get(pk=cliente_id)
            canal = CanalCliente.objects.get(canal_id=canal_id)
            sucursal = Sucursal.objects.get(sucursal_id=sucursal_id)  # Obtener sucursal
        except (Cliente.DoesNotExist, CanalCliente.DoesNotExist, Sucursal.DoesNotExist):
            messages.error(request, "Cliente, canal o sucursal no válidos.")
            return redirect("crear_pedido")

        # Crear el pedido principal
        pedido = Pedido.objects.create(
            cliente=cliente,
            canal=canal,
            sucursal=sucursal,  # Asignar la sucursal aquí
            fecha=timezone.now(),
        )

        total_pedido = 0  # Total del pedido

        # Crear los detalles del pedido
        for articulo_id, cantidad_str in zip(articulo_ids, cantidades):
            try:
                articulo = Articulo.objects.get(articulo_id=articulo_id)
                cantidad = int(cantidad_str)
            except (Articulo.DoesNotExist, ValueError):
                continue  # Si el artículo no existe o la cantidad no es válida, se omite

            # Calcular el subtotal para este artículo
            subtotal = cantidad * articulo.precio_unitario  # Usamos el precio real del artículo
            total_pedido += subtotal

            # Crear el detalle del pedido
            DetallePedido.objects.create(
                pedido=pedido,
                articulo=articulo,
                cantidad=cantidad,
                precio_unitario=articulo.precio_unitario,  # Usamos el precio real
                subtotal=subtotal
            )

        # Aplicar promociones si tienes la lógica
        aplicar_promociones(pedido)  # Asegúrate de definir esta función si tienes promociones

        # Recalcular el total del pedido después de aplicar las promociones
        pedido.total = total_pedido  # Sumar el total de los artículos y promociones (si hay)
        pedido.save()

        messages.success(request, "Pedido creado correctamente.")
        return redirect("listar_pedidos")  # Cambia al nombre de tu vista de pedidos

    # GET - Mostrar el formulario
    context = {
        "clientes": Cliente.objects.all(),
        "articulos": Articulo.objects.all(),
        "canales": CanalCliente.objects.all(),
        "sucursales": Sucursal.objects.all()  # Asegúrate de pasar las sucursales al contexto
    }
    return render(request, "core/ventas/formulario.html", context)