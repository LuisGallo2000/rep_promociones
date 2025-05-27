from rest_framework import serializers
from core.models import (
    Empresa, Sucursal, CanalCliente, GrupoProveedor, Linea, Articulo,
    Vendedor, Cliente, Promocion, CondicionPromocion, EscalaPromocion,
    BeneficioPromocion, Pedido, DetallePedido, PromocionAplicada
)

class EmpresaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Empresa
        fields = '__all__'

class SucursalSerializer(serializers.ModelSerializer):
    empresa_nombre = serializers.CharField(source='empresa.nombre', read_only=True)

    class Meta:
        model = Sucursal
        fields = ['sucursal_id', 'empresa', 'empresa_nombre', 'nombre']

class CanalClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CanalCliente
        fields = '__all__'

class GrupoProveedorSerializer(serializers.ModelSerializer):
    empresa_nombre = serializers.CharField(source='empresa.nombre', read_only=True)
    class Meta:
        model = GrupoProveedor
        fields = ['grupo_id', 'empresa', 'empresa_nombre', 'codigo', 'nombre', 'estado']

class LineaSerializer(serializers.ModelSerializer):
    empresa_nombre = serializers.CharField(source='empresa.nombre', read_only=True)
    grupo_nombre = serializers.CharField(source='grupo.nombre', read_only=True)
    class Meta:
        model = Linea
        fields = ['linea_id', 'empresa', 'empresa_nombre', 'grupo', 'grupo_nombre', 'codigo', 'nombre', 'estado']

class ArticuloSerializer(serializers.ModelSerializer):
    empresa_nombre = serializers.CharField(source='empresa.nombre', read_only=True)
    grupo_nombre = serializers.CharField(source='grupo.nombre', read_only=True, allow_null=True)
    linea_nombre = serializers.CharField(source='linea.nombre', read_only=True, allow_null=True)

    class Meta:
        model = Articulo
        fields = [
            'articulo_id', 'empresa', 'empresa_nombre', 'codigo_articulo', 'descripcion', 
            'grupo', 'grupo_nombre', 'linea', 'linea_nombre', 'unidad_medida', 
            'precio_venta' 
        ]

class ClienteSerializer(serializers.ModelSerializer):
    canal_nombre = serializers.CharField(source='canal.nombre', read_only=True, allow_null=True)
    tipo_cliente_display = serializers.CharField(source='get_tipo_cliente_display', read_only=True)

    class Meta:
        model = Cliente
        fields = [
            'cliente_id', 'nombres', 'canal', 'canal_nombre', 'nro_documento', 
            'tipo_documento', 'tipo_cliente', 'tipo_cliente_display'
        ]

# --- Serializadores para Promociones ---

class BeneficioPromocionSerializer(serializers.ModelSerializer):
    articulo_bonificado_desc = serializers.CharField(source='articulo_bonificado.descripcion', read_only=True, allow_null=True)
    class Meta:
        model = BeneficioPromocion
        fields = [
            'beneficiopromocion_id', 'tipo', 'articulo_bonificado', 'articulo_bonificado_desc',
            'cantidad_bonificada', 'porcentaje_descuento'
        ]

class EscalaPromocionSerializer(serializers.ModelSerializer):
    beneficios = BeneficioPromocionSerializer(many=True, read_only=True)

    class Meta:
        model = EscalaPromocion
        fields = [
            'escalapromocion_id', 'descripcion_escala', 'desde_monto', 'hasta_monto',
            'desde_cantidad', 'hasta_cantidad', 'proporcional', 
            'base_cantidad_proporcional_escala', 'base_monto_proporcional_escala',
            'beneficios'
        ]

class CondicionPromocionSerializer(serializers.ModelSerializer):
    articulo_desc = serializers.CharField(source='articulo.descripcion', read_only=True, allow_null=True)
    linea_nombre = serializers.CharField(source='linea.nombre', read_only=True, allow_null=True)
    grupo_nombre = serializers.CharField(source='grupo.nombre', read_only=True, allow_null=True)

    class Meta:
        model = CondicionPromocion
        fields = [
            'condicionpromocion_id', 'articulo', 'articulo_desc', 'linea', 'linea_nombre', 
            'grupo', 'grupo_nombre', 'cantidad_minima', 'monto_minimo', 'obligatoria_en_conjunto'
        ]

class PromocionSerializer(serializers.ModelSerializer):
    empresa_nombre = serializers.CharField(source='empresa.nombre', read_only=True)
    sucursal_nombre = serializers.CharField(source='sucursal.nombre', read_only=True, allow_null=True)
    canal_cliente_nombre = serializers.CharField(source='canal_cliente_aplicable.nombre', read_only=True, allow_null=True)
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    aplica_por_display = serializers.CharField(source='get_aplica_por_display', read_only=True)
    tipo_cliente_display = serializers.CharField(source='get_tipo_cliente_display', read_only=True)

    condiciones = CondicionPromocionSerializer(many=True, read_only=True)
    escalas = EscalaPromocionSerializer(many=True, read_only=True)
    beneficios_directos = BeneficioPromocionSerializer(many=True, read_only=True) 

    class Meta:
        model = Promocion
        fields = [
            'promocion_id', 'nombre', 'descripcion', 'empresa', 'empresa_nombre', 
            'sucursal', 'sucursal_nombre', 'canal_cliente_aplicable', 'canal_cliente_nombre',
            'fecha_inicio', 'fecha_fin', 'tipo', 'tipo_display', 'aplica_por', 'aplica_por_display',
            'es_escalonada', 'es_proporcional_directa', 'base_cantidad_proporcional_directa',
            'base_monto_proporcional_directa', 'tipo_cliente', 'tipo_cliente_display', 
            'activa', 'prioridad',
            'condiciones', 'escalas', 'beneficios_directos'
        ]

# --- Serializadores para Pedidos ---

class DetallePedidoSerializer(serializers.ModelSerializer):
    articulo_codigo = serializers.CharField(source='articulo.codigo_articulo', read_only=True)
    articulo_descripcion = serializers.CharField(source='articulo.descripcion', read_only=True)
    promocion_origen_nombre = serializers.CharField(source='promocion_origen.nombre', read_only=True, allow_null=True)

    class Meta:
        model = DetallePedido
        fields = [
            'detallepedido_id', 'articulo', 'articulo_codigo', 'articulo_descripcion', 
            'cantidad', 'precio_unitario_lista', 'subtotal_linea', 
            'descuento_linea', 'total_linea', 'es_bonificacion', 
            'promocion_origen', 'promocion_origen_nombre'
        ]
        read_only_fields = ['subtotal_linea', 'descuento_linea', 'total_linea', 'es_bonificacion', 'promocion_origen'] 


class PromocionAplicadaSerializer(serializers.ModelSerializer):
    promocion_nombre = serializers.CharField(source='promocion.nombre', read_only=True)
    escala_descripcion = serializers.CharField(source='escala_aplicada.descripcion_escala', read_only=True, allow_null=True)

    class Meta:
        model = PromocionAplicada
        fields = [
            'promocionaplicada_id', 'promocion', 'promocion_nombre', 'escala_aplicada', 'escala_descripcion',
            'descripcion_beneficios_obtenidos', 'monto_descuento_generado'
        ]


class PedidoSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source='cliente.nombres', read_only=True)
    canal_nombre = serializers.CharField(source='canal.nombre', read_only=True)
    sucursal_nombre = serializers.CharField(source='sucursal.nombre', read_only=True)
    
    detalles = DetallePedidoSerializer(many=True, required=False) 
    promociones_aplicadas = PromocionAplicadaSerializer(many=True, read_only=True)

    class Meta:
        model = Pedido
        fields = [
            'pedido_id', 'cliente', 'cliente_nombre', 'canal', 'canal_nombre', 
            'sucursal', 'sucursal_nombre', 'fecha', 'subtotal', 'descuento_total', 'total_pedido',
            'detalles', 'promociones_aplicadas'
        ]
        read_only_fields = ['fecha', 'subtotal', 'descuento_total', 'total_pedido', 'promociones_aplicadas']

    def create(self, validated_data):
        detalles_data = validated_data.pop('detalles', [])
        pedido = Pedido.objects.create(**validated_data)
        for detalle_data in detalles_data:
            DetallePedido.objects.create(pedido=pedido, **detalle_data)
        pedido.subtotal = sum(d.subtotal_linea for d in pedido.detalles.filter(es_bonificacion=False))
        pedido.total_pedido = pedido.subtotal 
        pedido.save()
        return pedido

    def update(self, instance, validated_data):
        instance.cliente = validated_data.get('cliente', instance.cliente)
        instance.canal = validated_data.get('canal', instance.canal)
        instance.sucursal = validated_data.get('sucursal', instance.sucursal)
        instance.save()

        instance.subtotal = sum(d.subtotal_linea for d in instance.detalles.filter(es_bonificacion=False))
        instance.total_pedido = instance.subtotal - instance.descuento_total
        instance.save()
        return instance