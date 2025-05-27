from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from decimal import Decimal
from django.utils import timezone

from core.models import (
    Empresa, Sucursal, CanalCliente, GrupoProveedor, Linea, Articulo,
    Vendedor, Cliente, Promocion, CondicionPromocion, EscalaPromocion,
    BeneficioPromocion, Pedido, DetallePedido, PromocionAplicada
)
from .serializers import (
    EmpresaSerializer, SucursalSerializer, CanalClienteSerializer, GrupoProveedorSerializer,
    LineaSerializer, ArticuloSerializer, ClienteSerializer, PromocionSerializer,
    PedidoSerializer, DetallePedidoSerializer
)

# --- ViewSets para Catálogos ---
class EmpresaViewSet(viewsets.ModelViewSet):
    queryset = Empresa.objects.all()
    serializer_class = EmpresaSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly] 

class SucursalViewSet(viewsets.ModelViewSet):
    queryset = Sucursal.objects.all()
    serializer_class = SucursalSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

class CanalClienteViewSet(viewsets.ModelViewSet):
    queryset = CanalCliente.objects.all()
    serializer_class = CanalClienteSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

class GrupoProveedorViewSet(viewsets.ModelViewSet):
    queryset = GrupoProveedor.objects.all()
    serializer_class = GrupoProveedorSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

class LineaViewSet(viewsets.ModelViewSet):
    queryset = Linea.objects.all()
    serializer_class = LineaSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

class ArticuloViewSet(viewsets.ModelViewSet):
    queryset = Articulo.objects.select_related('empresa', 'grupo', 'linea').all()
    serializer_class = ArticuloSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        descripcion = self.request.query_params.get('descripcion')
        codigo = self.request.query_params.get('codigo_articulo')
        if descripcion:
            queryset = queryset.filter(descripcion__icontains=descripcion)
        if codigo:
            queryset = queryset.filter(codigo_articulo__icontains=codigo)
        return queryset

class ClienteViewSet(viewsets.ModelViewSet):
    queryset = Cliente.objects.select_related('canal').all()
    serializer_class = ClienteSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class PromocionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Promocion.objects.prefetch_related(
        'condiciones__articulo', 'condiciones__linea', 'condiciones__grupo',
        'escalas__beneficios__articulo_bonificado', 
        'beneficios_directos__articulo_bonificado'
    ).all()
    serializer_class = PromocionSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

# --- ViewSet para Pedidos ---
class PedidoViewSet(viewsets.ModelViewSet):
    queryset = Pedido.objects.prefetch_related('detalles__articulo', 'promociones_aplicadas__promocion').all()
    serializer_class = PedidoSerializer
    permission_classes = [permissions.IsAuthenticated] 

    def perform_create(self, serializer):
        serializer.save(fecha=timezone.now())

    @action(detail=True, methods=['post'], url_path='aplicar-promociones')
    def aplicar_promociones(self, request, pk=None):
        """
        Endpoint para (re)aplicar promociones a un pedido existente.
        """
        pedido = self.get_object()
        
        try:
            pedido.subtotal = sum(d.subtotal_linea for d in pedido.detalles.filter(es_bonificacion=False))
            pedido.total_pedido = pedido.subtotal - pedido.descuento_total
            pedido.save()
            
            serializer = self.get_serializer(pedido)
            return Response(serializer.data)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DetallePedidoViewSet(viewsets.ModelViewSet):
    queryset = DetallePedido.objects.all()
    serializer_class = DetallePedidoSerializer
    permission_classes = [permissions.IsAuthenticated]