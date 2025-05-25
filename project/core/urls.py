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
    path('promociones/<int:pk>/editar/', views.editar_promocion, name='editar_promocion'),
    path('promociones/<int:pk>/eliminar/', views.eliminar_promocion, name='eliminar_promocion'),

    # Condiciones
    path('promociones/<int:pk>/condiciones/', views.gestionar_condiciones, name='gestionar_condiciones'),
    path('condiciones/<int:pk>/eliminar/', views.eliminar_condicion, name='eliminar_condicion'),

    # Beneficios
    path('promociones/<int:pk>/beneficios/', views.gestionar_beneficios, name='gestionar_beneficios'),
    path('beneficios/<int:pk>/eliminar/', views.eliminar_beneficio, name='eliminar_beneficio'),

    # Escalas
    path('promociones/<int:pk>/escalas/', views.gestionar_escalas, name='gestionar_escalas'),
    path('escalas/<int:pk>/eliminar/', views.eliminar_escala, name='eliminar_escala'),
]