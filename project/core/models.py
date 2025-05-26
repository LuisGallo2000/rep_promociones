from django.db import models
import uuid

# === CATÁLOGOS BASE ===

class Empresa(models.Model):
    empresa_id = models.CharField(primary_key=True, max_length=20)
    nombre = models.CharField(max_length=100, unique=True)
    def __str__(self):
        return self.nombre

class Sucursal(models.Model):
    sucursal_id = models.CharField(primary_key=True, max_length=20)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="sucursales")
    nombre = models.CharField(max_length=100)
    class Meta:
        unique_together = ('empresa', 'nombre')
    def __str__(self):
        return f"{self.empresa.nombre} - {self.nombre}"

class CanalCliente(models.Model):
    canal_id = models.CharField(primary_key=True, max_length=20)
    nombre = models.CharField(max_length=50, unique=True)
    def __str__(self):
        return self.nombre

class GrupoProveedor(models.Model):
    grupo_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="grupos_proveedor")
    codigo = models.CharField(max_length=20)
    nombre = models.CharField(max_length=100)
    estado = models.BooleanField(default=True)
    class Meta:
        # El código de grupo debe ser único dentro de una empresa si no es global
        unique_together = ('empresa', 'codigo')
    def __str__(self):
        return self.nombre

class Linea(models.Model):
    linea_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="lineas_producto")
    grupo = models.ForeignKey(GrupoProveedor, on_delete=models.CASCADE, related_name="lineas")
    codigo = models.CharField(max_length=20)
    nombre = models.CharField(max_length=100)
    estado = models.BooleanField(default=True)
    class Meta:
        # El código de línea debe ser único dentro de una empresa si no es global
        unique_together = ('empresa', 'codigo')
    def __str__(self):
        return self.nombre

class Articulo(models.Model):
    articulo_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="articulos")
    codigo_articulo = models.CharField(max_length=50)
    codigo_barras = models.CharField(max_length=50, null=True, blank=True)
    codigo_ean = models.CharField(max_length=50, null=True, blank=True)
    descripcion = models.TextField()
    grupo = models.ForeignKey(GrupoProveedor, on_delete=models.SET_NULL, null=True, blank=True, related_name="articulos")
    linea = models.ForeignKey(Linea, on_delete=models.SET_NULL, null=True, blank=True, related_name="articulos")
    unidad_medida = models.CharField(max_length=20)
    unidad_compra = models.CharField(max_length=20, null=True, blank=True)
    unidad_reparto = models.CharField(max_length=20, null=True, blank=True)
    unidad_bonificacion = models.CharField(max_length=20, null=True, blank=True)
    factor_reparto = models.IntegerField(null=True, blank=True)
    factor_compra = models.IntegerField(null=True, blank=True)
    factor_bonificacion = models.IntegerField(null=True, blank=True)
    tipo_afectacion = models.CharField(max_length=20)
    peso = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    tipo_producto = models.CharField(max_length=50)
    afecto_retencion = models.BooleanField(default=False)
    afecto_detraccion = models.BooleanField(default=False)
    precio_venta = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True,
        blank=True,
        help_text="Precio de venta unitario del artículo. Puede ser nulo y especificarse en el pedido."
    )
    class Meta:
        unique_together = ('empresa', 'codigo_articulo')
    def __str__(self):
        return f"{self.codigo_articulo} - {self.descripcion}"

class Vendedor(models.Model):
    nro_documento = models.CharField(max_length=20, primary_key=True)
    tipo_identificacion_id = models.IntegerField()
    nombres = models.CharField(max_length=100)
    direccion = models.TextField(null=True, blank=True)
    nro_movil = models.CharField(max_length=20, null=True, blank=True)
    canal = models.ForeignKey(CanalCliente, on_delete=models.SET_NULL, null=True, blank=True, related_name="vendedores")
    supervisor = models.CharField(max_length=100, null=True, blank=True)
    correo_electronico = models.EmailField(null=True, blank=True)
    territorio = models.CharField(max_length=100, null=True, blank=True)
    rol_id = models.IntegerField(null=True, blank=True)
    def __str__(self):
        return self.nombres

# === CLIENTE ===
class Cliente(models.Model):
    TIPO_CLIENTE_CHOICES = [
        ('mayorista', 'Mayorista'),
        ('cobertura', 'Cobertura'),
        ('mercado', 'Mercado'),
        ('institucional', 'Institucional'),
        ('todos', 'Todos')
    ]
    cliente_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nombres = models.CharField(max_length=255)
    canal = models.ForeignKey(CanalCliente, on_delete=models.SET_NULL, null=True, blank=True, related_name="clientes")
    nro_documento = models.CharField(max_length=20, unique=True)
    tipo_documento = models.CharField(max_length=10)
    tipo_cliente = models.CharField(max_length=20, choices=TIPO_CLIENTE_CHOICES, default='todos', help_text="Clasificación del cliente para promociones.")
    def __str__(self):
        return f"{self.nro_documento} - {self.nombres}"

# === PROMOCIONES ===

class Promocion(models.Model):
    TIPO_PROMOCION_CHOICES = [
        ('bonificacion', 'Bonificación'),
        ('descuento', 'Descuento'),
        ('combinado', 'Combinado')
    ]
    APLICA_POR_CHOICES = [
        ('productos_condicion', 'Cantidad/Monto de Productos en Condición'),
        ('total_pedido', 'Monto Total del Pedido'),
        ('conjunto_obligatorio', 'Compra Conjunta de Productos Específicos')
    ]
    promocion_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nombre = models.CharField(max_length=150, unique=True) # Nombre único para fácil identificación
    descripcion = models.TextField(null=True, blank=True)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="promociones")
    sucursal = models.ForeignKey(Sucursal, on_delete=models.SET_NULL, null=True, blank=True, help_text="Si vacío, aplica a todas las sucursales de la empresa.", related_name="promociones")
    canal_cliente_aplicable = models.ForeignKey(CanalCliente, on_delete=models.SET_NULL, null=True, blank=True, help_text="Si vacío, aplica a todos los canales.", related_name="promociones")
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    tipo = models.CharField(max_length=20, choices=TIPO_PROMOCION_CHOICES)
    aplica_por = models.CharField(max_length=30, choices=APLICA_POR_CHOICES)
    es_escalonada = models.BooleanField(default=False)
    es_proporcional_directa = models.BooleanField(default=False, help_text="Si no es escalonada, ¿es proporcional?")
    base_cantidad_proporcional_directa = models.IntegerField(null=True, blank=True)
    base_monto_proporcional_directa = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tipo_cliente = models.CharField(max_length=20, choices=Cliente.TIPO_CLIENTE_CHOICES, default='todos')
    activa = models.BooleanField(default=True)
    prioridad = models.IntegerField(default=0, help_text="Menor número, mayor prioridad.")

    def __str__(self):
        return self.nombre

class CondicionPromocion(models.Model):
    condicionpromocion_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) # Renombrado
    promocion = models.ForeignKey(Promocion, on_delete=models.CASCADE, related_name="condiciones")
    articulo = models.ForeignKey(Articulo, on_delete=models.CASCADE, null=True, blank=True, related_name="condiciones_promocion")
    linea = models.ForeignKey(Linea, on_delete=models.CASCADE, null=True, blank=True, related_name="condiciones_promocion")
    grupo = models.ForeignKey(GrupoProveedor, on_delete=models.CASCADE, null=True, blank=True, related_name="condiciones_promocion")
    cantidad_minima = models.IntegerField(null=True, blank=True)
    monto_minimo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    obligatoria_en_conjunto = models.BooleanField(default=False, help_text="Si promo es 'conjunto_obligatorio', este item es mandatorio.")

    def __str__(self):
        target = "Condición General"
        if self.articulo: target = self.articulo.codigo_articulo
        elif self.linea: target = self.linea.nombre
        elif self.grupo: target = self.grupo.nombre
        return f"Condición para '{self.promocion.nombre}' sobre '{target}'"

class EscalaPromocion(models.Model):
    escalapromocion_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) # Renombrado
    promocion = models.ForeignKey(Promocion, on_delete=models.CASCADE, related_name="escalas")
    descripcion_escala = models.CharField(max_length=100, null=True, blank=True)
    desde_monto = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    hasta_monto = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    desde_cantidad = models.IntegerField(null=True, blank=True)
    hasta_cantidad = models.IntegerField(null=True, blank=True)
    proporcional = models.BooleanField(default=False, help_text="¿Esta escala aplica beneficio proporcionalmente?")
    base_cantidad_proporcional_escala = models.IntegerField(null=True, blank=True)
    base_monto_proporcional_escala = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"Escala para '{self.promocion.nombre}' ({self.descripcion_escala or self.escalapromocion_id})"

class BeneficioPromocion(models.Model):
    TIPO_BENEFICIO_CHOICES = [
        ('bonificacion', 'Bonificación de Producto'),
        ('descuento', 'Descuento en Porcentaje')
    ]
    beneficiopromocion_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) # Renombrado
    promocion = models.ForeignKey(Promocion, on_delete=models.CASCADE, related_name="beneficios_directos", null=True, blank=True)
    escala = models.ForeignKey(EscalaPromocion, on_delete=models.CASCADE, related_name="beneficios", null=True, blank=True)
    tipo = models.CharField(max_length=20, choices=TIPO_BENEFICIO_CHOICES)
    articulo_bonificado = models.ForeignKey(Articulo, on_delete=models.SET_NULL, null=True, blank=True, related_name="es_bonificacion_en")
    cantidad_bonificada = models.IntegerField(null=True, blank=True)
    porcentaje_descuento = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    def __str__(self):
        owner = "Beneficio Huérfano" # Default, debería tener promo o escala
        if self.promocion: owner = f"Promo directa '{self.promocion.nombre}'"
        elif self.escala: owner = f"Escala '{self.escala.descripcion_escala or self.escala.escalapromocion_id}' de Promo '{self.escala.promocion.nombre}'"
        
        if self.tipo == 'bonificacion' and self.articulo_bonificado:
            return f"Bonif. {self.cantidad_bonificada}x {self.articulo_bonificado.codigo_articulo} para {owner}"
        elif self.tipo == 'descuento':
            return f"Desc. {self.porcentaje_descuento}% para {owner}"
        return f"Beneficio ({self.beneficiopromocion_id}) para {owner}"

# === PEDIDOS ===
class Pedido(models.Model):
    pedido_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="pedidos")
    canal = models.ForeignKey(CanalCliente, on_delete=models.PROTECT, related_name="pedidos")
    sucursal = models.ForeignKey(Sucursal, on_delete=models.PROTECT, related_name="pedidos")
    fecha = models.DateTimeField(auto_now_add=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    descuento_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_pedido = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # Considerar añadir un campo vendedor = models.ForeignKey(Vendedor, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Pedido {self.pedido_id} de {self.cliente.nombres}"

class DetallePedido(models.Model):
    detallepedido_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) # Renombrado
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="detalles")
    articulo = models.ForeignKey(Articulo, on_delete=models.PROTECT, related_name="en_pedidos")
    cantidad = models.PositiveIntegerField() # Cantidad debe ser positiva
    precio_unitario_lista = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal_linea = models.DecimalField(max_digits=12, decimal_places=2) # cantidad * precio_unitario_lista
    descuento_linea = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_linea = models.DecimalField(max_digits=12, decimal_places=2) # subtotal_linea - descuento_linea
    es_bonificacion = models.BooleanField(default=False, help_text="True si este item es bonificación y precio es 0.")
    promocion_origen = models.ForeignKey(Promocion, on_delete=models.SET_NULL, null=True, blank=True, help_text="Promoción que originó este ítem si es bonificación.", related_name="items_bonificados_generados")

    def save(self, *args, **kwargs):
        # Calcular subtotal y total de línea automáticamente si no es bonificación
        if not self.es_bonificacion:
            self.subtotal_linea = self.cantidad * self.precio_unitario_lista
            self.total_linea = self.subtotal_linea - self.descuento_linea
        else: # Si es bonificación, los precios y montos deberían ser 0
            self.precio_unitario_lista = 0
            self.subtotal_linea = 0
            self.descuento_linea = 0
            self.total_linea = 0
        super().save(*args, **kwargs)

    def __str__(self):
        prefix = "[BONIF] " if self.es_bonificacion else ""
        return f"{prefix}{self.cantidad} x {self.articulo.codigo_articulo} en Pedido {self.pedido.pedido_id}"

class PromocionAplicada(models.Model):
    promocionaplicada_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="promociones_aplicadas")
    promocion = models.ForeignKey(Promocion, on_delete=models.PROTECT, related_name="aplicaciones_en_pedidos")
    escala_aplicada = models.ForeignKey(EscalaPromocion, on_delete=models.SET_NULL, null=True, blank=True, help_text="Escala específica que se activó.", related_name="aplicaciones_en_pedidos")
    descripcion_beneficios_obtenidos = models.TextField(null=True, blank=True)
    monto_descuento_generado = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"Promo '{self.promocion.nombre}' aplicada a Pedido {self.pedido.pedido_id}"