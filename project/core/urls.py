from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),

    path('dashboard/', views.dashboard, name='dashboard'),

    # Autenticación
    path('login/', views.login_user, name='login_user'),
    path('logout/', views.logout_user, name='logout_user'),

    # --- PROMOCIONES ---
    path('promociones/', views.listar_promociones, name='listar_promociones'),
    path('promociones/gestionar/', views.gestionar_promocion_completa, name='crear_promocion_completa'),
    path('promociones/gestionar/<uuid:promocion_id>/', views.gestionar_promocion_completa, name='editar_promocion_completa'),
    path('promociones/detalle/<uuid:promocion_id>/', views.detalle_promocion, name='detalle_promocion'),
    path('promociones/eliminar/<uuid:promocion_id>/', views.eliminar_promocion, name='eliminar_promocion'),
    # --- BÚSQUEDAS JSON (para autocompletar en formularios) ---
    path('buscar-articulos-json/', views.buscar_articulos_json, name='buscar_articulos_json'),

    # --- PEDIDOS ---
    path('pedidos/', views.listar_pedidos, name='listar_pedidos'),
    path('pedidos/crear/', views.crear_pedido_vista, name='crear_pedido_vista'),
    path('pedidos/detalle/<uuid:pedido_id>/', views.vista_detalle_pedido, name='vista_detalle_pedido'),
    path('pedidos/aplicar-promociones/<uuid:pedido_id>/', views.procesar_y_aplicar_promociones_a_pedido, name='procesar_promociones_pedido'),

    path('buscar-articulos-json/', views.buscar_articulos_json, name='buscar_articulos_json'),
    path('buscar-lineas-json/', views.buscar_lineas_json, name='buscar_lineas_json'),
    path('buscar-grupos-json/', views.buscar_grupos_json, name='buscar_grupos_json'),

    path('promociones/escalas/<uuid:escala_id>/gestionar-beneficios/', views.gestionar_beneficios_de_escala, name='gestionar_beneficios_escala'),
]