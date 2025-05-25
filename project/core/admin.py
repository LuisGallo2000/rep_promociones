from django.contrib import admin
from .models import CondicionPromocion, Articulo, Linea, GrupoProveedor

@admin.register(Articulo)
class ArticuloAdmin(admin.ModelAdmin):
    search_fields = ['nombre']  
@admin.register(Linea)
class LineaAdmin(admin.ModelAdmin):
    search_fields = ['nombre']

@admin.register(GrupoProveedor)
class GrupoProveedorAdmin(admin.ModelAdmin):
    search_fields = ['nombre']

@admin.register(CondicionPromocion)
class CondicionPromocionAdmin(admin.ModelAdmin):
    autocomplete_fields = ['articulo', 'linea', 'grupo']