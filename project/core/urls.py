from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),

    # Autenticación
    path('login/', views.login_user, name='login'),
    path('logout/', views.logout_user, name='logout'),

    # Promociones
    path('promociones/', views.listar_promociones, name='listar_promociones'),
    path('promociones/crear/', views.crear_promocion, name='crear_promocion'),
    path('promociones/<int:pk>/', views.detalle_promocion, name='detalle_promocion'),
    path('promociones/<int:pk>/editar/', views.editar_promocion, name='editar_promocion'),
    path('promociones/<int:pk>/eliminar/', views.eliminar_promocion, name='eliminar_promocion'),

    # Condiciones
    path('promociones/<int:promocion_id>/condiciones/crear/', views.crear_condicion, name='crear_condicion'),
    path('promociones/<int:pk>/condiciones/', views.gestionar_condiciones, name='gestionar_condiciones'),
    path('condiciones/<int:pk>/eliminar/', views.eliminar_condicion, name='eliminar_condicion'),
    
    path('buscar-articulo/', views.buscar_articulo, name='buscar_articulo'),
    path('buscar-linea/', views.buscar_linea, name='buscar_linea'),
    path('buscar-grupo/', views.buscar_grupo, name='buscar_grupo'),


    # Beneficios
    path('promociones/<int:pk>/beneficios/', views.gestionar_beneficios, name='gestionar_beneficios'),
    path('beneficios/<int:pk>/eliminar/', views.eliminar_beneficio, name='eliminar_beneficio'),

    # Escalas
    path('promociones/<int:pk>/escalas/', views.gestionar_escalas, name='gestionar_escalas'),
    path('escalas/<int:pk>/eliminar/', views.eliminar_escala, name='eliminar_escala'),
    path('promociones/<int:promocion_id>/condiciones/<int:condicion_id>/escalas/crear/', views.crear_escala, name='crear_escala'),
    path('api/buscar_articulos/', views.buscar_articulos, name='buscar_articulos'),

    # Pedidos
    path('pedidos/crear/', views.crear_pedido, name='crear_pedido'),

]