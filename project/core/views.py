from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from decimal import Decimal
from django.db.models import Q, Sum, F

from .models import (
    Promocion, Pedido, DetallePedido, PromocionAplicada,
    CondicionPromocion, BeneficioPromocion, EscalaPromocion, Articulo
)
from .forms import PromocionForm


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
            return redirect('dashboard')
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
            total_monto = detalles_filtrados.aggregate(
                total=Sum(F('cantidad') * F('precio_unitario'))
            )['total'] or 0

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

@login_required
def crear_condicion(request, promocion_id):
    promocion = get_object_or_404(Promocion, id=promocion_id)
    if request.method == 'POST':
        articulo_id = request.POST.get('articulo')
        linea_id = request.POST.get('linea')
        grupo_id = request.POST.get('grupo')
        cantidad_minima = request.POST.get('cantidad_minima') or None
        monto_minimo = request.POST.get('monto_minimo') or None
        cantidad_maxima = request.POST.get('cantidad_maxima') or None
        monto_maximo = request.POST.get('monto_maximo') or None
        obligatoria = 'obligatoria' in request.POST

        CondicionPromocion.objects.create(
            promocion=promocion,
            articulo_id=articulo_id if articulo_id else None,
            linea_id=linea_id if linea_id else None,
            grupo_id=grupo_id if grupo_id else None,
            cantidad_minima=cantidad_minima,
            monto_minimo=monto_minimo,
            cantidad_maxima=cantidad_maxima,
            monto_maximo=monto_maximo,
            obligatoria=obligatoria
        )
        messages.success(request, "Condición registrada.")
        return redirect('detalle_promocion', pk=promocion.id)

    return render(request, 'core/condiciones/formulario.html', {'promocion': promocion})

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
