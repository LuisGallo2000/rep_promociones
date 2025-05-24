from django.db import models

# === CATÁLOGOS BASE ===

class Empresa(models.Model):
    nombre = models.CharField(max_length=100)

class Sucursal(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100)

class CanalCliente(models.Model):
    nombre = models.CharField(max_length=50)

class GrupoProveedor(models.Model):
    grupo_id = models.IntegerField(primary_key=True)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    codigo = models.CharField(max_length=20)
    nombre = models.CharField(max_length=100)
    estado = models.BooleanField(default=True)

class Linea(models.Model):
    linea_id = models.IntegerField(primary_key=True)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    grupo = models.ForeignKey(GrupoProveedor, on_delete=models.CASCADE)
    codigo = models.CharField(max_length=20)
    nombre = models.CharField(max_length=100)

class Articulo(models.Model):
    articulo_id = models.IntegerField(primary_key=True)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    codigo_articulo = models.CharField(max_length=50)
    codigo_barras = models.CharField(max_length=50, null=True, blank=True)
    codigo_ean = models.CharField(max_length=50, null=True, blank=True)
    descripcion = models.TextField()
    grupo = models.ForeignKey(GrupoProveedor, on_delete=models.SET_NULL, null=True, blank=True)
    linea = models.ForeignKey(Linea, on_delete=models.SET_NULL, null=True, blank=True)
    unidad_medida = models.CharField(max_length=20)
    unidad_compra = models.CharField(max_length=20)
    unidad_reparto = models.CharField(max_length=20)
    unidad_bonificacion = models.CharField(max_length=20)
    factor_reparto = models.IntegerField()
    factor_compra = models.IntegerField()
    factor_bonificacion = models.IntegerField()
    tipo_afectacion = models.CharField(max_length=20)
    peso = models.DecimalField(max_digits=10, decimal_places=3)
    tipo_producto = models.CharField(max_length=50)
    afecto_retencion = models.BooleanField()
    afecto_detraccion = models.BooleanField()

class Vendedor(models.Model):
    nro_documento = models.CharField(max_length=20, primary_key=True)
    tipo_identificacion_id = models.IntegerField()
    nombres = models.CharField(max_length=100)
    direccion = models.TextField()
    nro_movil = models.CharField(max_length=20)
    canal = models.ForeignKey(CanalCliente, on_delete=models.SET_NULL, null=True)
    supervisor = models.CharField(max_length=100)
    correo_electronico = models.EmailField()
    territorio = models.CharField(max_length=100)
    rol_id = models.IntegerField()


# === PROMOCIONES ===

class Promocion(models.Model):
    TIPO_PROMOCION = [
        ('bonificacion', 'Bonificación'),
        ('descuento', 'Descuento'),
        ('combinado', 'Combinado')
    ]
    APLICA_POR = [
        ('monto', 'Monto Total'),
        ('cantidad', 'Cantidad Total'),
        ('monto_producto', 'Monto Producto'),
        ('cantidad_producto', 'Cantidad Producto'),
        ('mixto', 'Mixto'),
    ]
    
    nombre = models.CharField(max_length=150)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    sucursal = models.ForeignKey(Sucursal, on_delete=models.SET_NULL, null=True, blank=True)
    canal = models.ForeignKey(CanalCliente, on_delete=models.CASCADE)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    tipo = models.CharField(max_length=20, choices=TIPO_PROMOCION)
    aplica_por = models.CharField(max_length=30, choices=APLICA_POR)
    es_escalonada = models.BooleanField(default=False)

class CondicionPromocion(models.Model):
    promocion = models.ForeignKey(Promocion, on_delete=models.CASCADE)
    articulo = models.ForeignKey(Articulo, on_delete=models.SET_NULL, null=True, blank=True)
    linea = models.ForeignKey(Linea, on_delete=models.SET_NULL, null=True, blank=True)
    cantidad_minima = models.IntegerField(null=True, blank=True)
    monto_minimo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cantidad_maxima = models.IntegerField(null=True, blank=True)
    monto_maximo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    obligatoria = models.BooleanField(default=False)

class BeneficioPromocion(models.Model):
    TIPO_BENEFICIO = [
        ('bonificacion', 'Bonificación'),
        ('descuento', 'Descuento')
    ]
    
    promocion = models.ForeignKey(Promocion, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=20, choices=TIPO_BENEFICIO)
    articulo = models.ForeignKey(Articulo, on_delete=models.SET_NULL, null=True, blank=True)
    cantidad = models.IntegerField(null=True, blank=True)
    porcentaje_descuento = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

class EscalaPromocion(models.Model):
    promocion = models.ForeignKey(Promocion, on_delete=models.CASCADE)
    condicion = models.ForeignKey(CondicionPromocion, on_delete=models.CASCADE)
    beneficio = models.ForeignKey(BeneficioPromocion, on_delete=models.CASCADE)
    desde_monto = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    hasta_monto = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    desde_cantidad = models.IntegerField(null=True, blank=True)
    hasta_cantidad = models.IntegerField(null=True, blank=True)


# === PEDIDOS ===

class Cliente(models.Model):
    nombres = models.CharField(max_length=100)
    canal = models.ForeignKey(CanalCliente, on_delete=models.SET_NULL, null=True, blank=True)
    nro_documento = models.CharField(max_length=20)
    tipo_documento = models.CharField(max_length=10)

class Pedido(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    canal = models.ForeignKey(CanalCliente, on_delete=models.CASCADE)
    sucursal = models.ForeignKey(Sucursal, on_delete=models.CASCADE)
    fecha = models.DateField(auto_now_add=True)

class DetallePedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE)
    articulo = models.ForeignKey(Articulo, on_delete=models.CASCADE)
    cantidad = models.IntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)

class PromocionAplicada(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE)
    promocion = models.ForeignKey(Promocion, on_delete=models.CASCADE)
    descuento_aplicado = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_bonificado = models.DecimalField(max_digits=10, decimal_places=2, default=0)