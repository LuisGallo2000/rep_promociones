from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'empresas', views.EmpresaViewSet, basename='empresa')
router.register(r'sucursales', views.SucursalViewSet, basename='sucursal')
router.register(r'canales-cliente', views.CanalClienteViewSet, basename='canalcliente')
router.register(r'grupos-proveedor', views.GrupoProveedorViewSet, basename='grupoproveedor')
router.register(r'lineas', views.LineaViewSet, basename='linea')
router.register(r'articulos', views.ArticuloViewSet, basename='articulo')
router.register(r'clientes', views.ClienteViewSet, basename='cliente')
router.register(r'promociones', views.PromocionViewSet, basename='promocion')
router.register(r'pedidos', views.PedidoViewSet, basename='pedido')
router.register(r'detalles-pedido', views.DetallePedidoViewSet, basename='detallepedido')

urlpatterns = [
    path('', include(router.urls)),
]