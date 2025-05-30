from django import forms
from django.forms import inlineformset_factory
from .models import (
    Empresa, Sucursal, CanalCliente, GrupoProveedor, Linea, Articulo,
    Vendedor, Cliente, Promocion, CondicionPromocion, EscalaPromocion,
    BeneficioPromocion, Pedido, DetallePedido, PromocionAplicada
)

class CondicionPromocionModelForm(forms.ModelForm):
    articulo_search = forms.CharField(
        label='Buscar Artículo (Condición)', 
        required=False, 
        widget=forms.TextInput(attrs={'class': 'form-control articulo-search-input', 'placeholder': 'Buscar artículo...'})
    )
    linea_search = forms.CharField(
        label='Buscar Línea (Condición)', 
        required=False, 
        widget=forms.TextInput(attrs={'class': 'form-control linea-search-input', 'placeholder': 'Buscar línea...'})
    )
    grupo_search = forms.CharField(
        label='Buscar Grupo/Marca (Condición)', 
        required=False, 
        widget=forms.TextInput(attrs={'class': 'form-control grupo-search-input', 'placeholder': 'Buscar grupo...'})
    )

    class Meta:
        model = CondicionPromocion
        fields = [
            'articulo', 'linea', 'grupo', 
            'cantidad_minima', 'monto_minimo', 'obligatoria_en_conjunto',
            'articulo_search', 'linea_search', 'grupo_search'
        ]
        widgets = {
            'articulo': forms.HiddenInput(attrs={'class': 'articulo-pk-input'}),
            'linea': forms.HiddenInput(attrs={'class': 'linea-pk-input'}),
            'grupo': forms.HiddenInput(attrs={'class': 'grupo-pk-input'}),
            'cantidad_minima': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Cant. Mín.'}),
            'monto_minimo': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Monto Mín.'}),
            'obligatoria_en_conjunto': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.articulo:
                self.initial['articulo_search'] = f"E:{self.instance.articulo.empresa.empresa_id} | {self.instance.articulo.codigo_articulo} - {self.instance.articulo.descripcion}"
            if self.instance.linea:
                self.initial['linea_search'] = self.instance.linea.nombre
            if self.instance.grupo:
                self.initial['grupo_search'] = self.instance.grupo.nombre
        
        self.fields['articulo'].required = False
        self.fields['linea'].required = False
        self.fields['grupo'].required = False

    def clean(self):
        cleaned_data = super().clean()
        # Si un campo de búsqueda tiene valor pero el campo FK no (porque JS falló o no se seleccionó),
        
        # Lógica para asegurar que solo uno de articulo, linea o grupo esté seleccionado para una condición:
        selected_targets = 0
        if cleaned_data.get('articulo'): selected_targets += 1
        if cleaned_data.get('linea'): selected_targets += 1
        if cleaned_data.get('grupo'): selected_targets += 1

        if selected_targets > 1:
            raise forms.ValidationError("Por favor, seleccione solo un Artículo, o una Línea, o un Grupo para la condición, no múltiples.")
        return cleaned_data


class BeneficioPromocionModelForm(forms.ModelForm):
    articulo_bonificado_search = forms.CharField(
        label='Buscar Artículo (Bonificación)', 
        required=False, 
        widget=forms.TextInput(attrs={'class': 'form-control articulo-bonificado-search-input', 'placeholder': 'Buscar artículo...'})
    )

    class Meta:
        model = BeneficioPromocion
        exclude = ['promocion', 'escala', 'beneficiopromocion_id']
        fields = [
            'tipo', 'articulo_bonificado', 'cantidad_bonificada', 'porcentaje_descuento',
            'articulo_bonificado_search'
        ]
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select tipo-beneficio'}),
            'articulo_bonificado': forms.HiddenInput(attrs={'class': 'articulo-bonificado-pk-input'}),
            'cantidad_bonificada': forms.NumberInput(attrs={'class': 'form-control cantidad-bonificada', 'placeholder': 'Cantidad'}),
            'porcentaje_descuento': forms.NumberInput(attrs={'class': 'form-control porcentaje-descuento', 'step': '0.01', 'placeholder': 'Porcentaje'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.articulo_bonificado:
            self.initial['articulo_bonificado_search'] = f"E:{self.instance.articulo_bonificado.empresa.empresa_id} | {self.instance.articulo_bonificado.codigo_articulo} - {self.instance.articulo_bonificado.descripcion}"
        
        self.fields['articulo_bonificado'].required = False
        self.fields['cantidad_bonificada'].required = False
        self.fields['porcentaje_descuento'].required = False

    def clean(self):
        cleaned_data = super().clean()
        tipo = cleaned_data.get("tipo")

        if tipo == "bonificacion":
            if not cleaned_data.get("articulo_bonificado"):
                if cleaned_data.get("articulo_bonificado_search"):
                     self.add_error('articulo_bonificado_search', 'Debe seleccionar un artículo válido de la lista.')
                else:
                     self.add_error('articulo_bonificado_search', 'Este campo es requerido para bonificación.')

            if not cleaned_data.get("cantidad_bonificada"):
                self.add_error('cantidad_bonificada', 'Este campo es requerido para bonificación.')
        elif tipo == "descuento":
            if not cleaned_data.get("porcentaje_descuento"):
                self.add_error('porcentaje_descuento', 'Este campo es requerido para descuento.')
        return cleaned_data

# === FORMULARIOS BÁSICOS DE CATÁLOGOS ===

class EmpresaForm(forms.ModelForm):
    class Meta:
        model = Empresa
        fields = ['nombre']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
        }

class SucursalForm(forms.ModelForm):
    class Meta:
        model = Sucursal
        fields = ['empresa', 'nombre']
        widgets = {
            'empresa': forms.Select(attrs={'class': 'form-select'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
        }

class CanalClienteForm(forms.ModelForm):
    class Meta:
        model = CanalCliente
        fields = ['canal_id', 'nombre']
        widgets = {
            'canal_id': forms.TextInput(attrs={'class': 'form-control'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
        }

class GrupoProveedorForm(forms.ModelForm):
    class Meta:
        model = GrupoProveedor
        fields = ['empresa', 'codigo', 'nombre', 'estado']
        widgets = {
            'empresa': forms.Select(attrs={'class': 'form-select'}),
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'estado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class LineaForm(forms.ModelForm):
    class Meta:
        model = Linea
        fields = ['empresa', 'grupo', 'codigo', 'nombre', 'estado']
        widgets = {
            'empresa': forms.Select(attrs={'class': 'form-select'}),
            'grupo': forms.Select(attrs={'class': 'form-select'}),
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'estado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class ArticuloForm(forms.ModelForm):
    class Meta:
        model = Articulo
        fields = [ 
            'empresa', 'codigo_articulo', 'codigo_barras', 'codigo_ean',
            'descripcion', 'grupo', 'linea', 'unidad_medida', 'unidad_compra',
            'unidad_reparto', 'unidad_bonificacion', 'factor_reparto',
            'factor_compra', 'factor_bonificacion', 'tipo_afectacion', 'peso',
            'tipo_producto', 'afecto_retencion', 'afecto_detraccion'
        ]
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'empresa': forms.Select(attrs={'class': 'form-select'}),
            'codigo_articulo': forms.TextInput(attrs={'class': 'form-control'}),
            'grupo': forms.Select(attrs={'class': 'form-select'}),
            'linea': forms.Select(attrs={'class': 'form-select'}),
        }

class VendedorForm(forms.ModelForm):
    class Meta:
        model = Vendedor
        fields = [
            'nro_documento', 'tipo_identificacion_id', 'nombres', 'direccion',
            'nro_movil', 'canal', 'supervisor', 'correo_electronico', 'territorio', 'rol_id'
        ]

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombres', 'canal', 'nro_documento', 'tipo_documento', 'tipo_cliente']


# === FORMULARIOS DE PROMOCIONES Y SUS ELEMENTOS ANIDADOS ===

class PromocionModelForm(forms.ModelForm):
    class Meta:
        model = Promocion
        fields = [
            'nombre', 'descripcion', 'empresa', 'sucursal', 'canal_cliente_aplicable',
            'fecha_inicio', 'fecha_fin', 'tipo', 'aplica_por', 'es_escalonada',
            'es_proporcional_directa', 'base_cantidad_proporcional_directa',
            'base_monto_proporcional_directa', 'tipo_cliente', 'activa', 'prioridad'
        ]
        widgets = {
            'fecha_inicio': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'fecha_fin': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'empresa': forms.Select(attrs={'class': 'form-select'}),
            'sucursal': forms.Select(attrs={'class': 'form-select'}),
            'canal_cliente_aplicable': forms.Select(attrs={'class': 'form-select'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'aplica_por': forms.Select(attrs={'class': 'form-select'}),
            'tipo_cliente': forms.Select(attrs={'class': 'form-select'}),
            'base_cantidad_proporcional_directa': forms.NumberInput(attrs={'class': 'form-control'}),
            'base_monto_proporcional_directa': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'prioridad': forms.NumberInput(attrs={'class': 'form-control'}),
            'es_escalonada': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'es_proporcional_directa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class EscalaPromocionModelForm(forms.ModelForm):
    class Meta:
        model = EscalaPromocion
        exclude = ['promocion', 'escalapromocion_id']
        fields = [
            'descripcion_escala', 'desde_monto', 'hasta_monto', 
            'desde_cantidad', 'hasta_cantidad', 'proporcional',
            'base_cantidad_proporcional_escala', 'base_monto_proporcional_escala',
        ]
        widgets = {
            'descripcion_escala': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: De 10 a 20 unidades'}),
            'desde_monto': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'hasta_monto': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'desde_cantidad': forms.NumberInput(attrs={'class': 'form-control'}),
            'hasta_cantidad': forms.NumberInput(attrs={'class': 'form-control'}),
            'proporcional': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

EscalaPromocionFormSet = inlineformset_factory(
    Promocion,
    EscalaPromocion,
    form=EscalaPromocionModelForm, 
    extra=1,
    can_delete=True,
    fk_name='promocion'
)

EscalaPromocionFormSet = inlineformset_factory(
    Promocion,
    EscalaPromocion,
    form=EscalaPromocionModelForm, 
    extra=1,
    can_delete=True,
    fk_name='promocion'
)


CondicionPromocionFormSet = inlineformset_factory(
    Promocion,
    CondicionPromocion,
    form=CondicionPromocionModelForm,
    extra=1,
    can_delete=True,
    fk_name='promocion'
)

BeneficioDirectoPromocionFormSet = inlineformset_factory(
    Promocion,
    BeneficioPromocion,
    form=BeneficioPromocionModelForm,
    fk_name='promocion',
    extra=1,
    can_delete=True
)

BeneficioEscalaPromocionFormSet = inlineformset_factory(
    EscalaPromocion,
    BeneficioPromocion,
    form=BeneficioPromocionModelForm,
    fk_name='escala',
    extra=1,
    can_delete=True
)


# === FORMULARIOS DE PEDIDOS ===

class PedidoModelForm(forms.ModelForm):
    class Meta:
        model = Pedido
        exclude = ['pedido_id', 'subtotal', 'descuento_total', 'total_pedido', 'fecha']
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-select'}),
            'canal': forms.Select(attrs={'class': 'form-select'}),
            'sucursal': forms.Select(attrs={'class': 'form-select'}),
        }

class DetallePedidoModelForm(forms.ModelForm):
    class Meta:
        model = DetallePedido
        exclude = [
            'detallepedido_id', 'pedido', 'subtotal_linea',
            'descuento_linea', 'total_linea', 'es_bonificacion', 'promocion_origen'
        ]
        widgets = {
            'articulo': forms.Select(attrs={'class': 'form-select select-articulo-pedido'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'precio_unitario_lista': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'readonly': 'readonly'}),
        }

DetallePedidoFormSet = inlineformset_factory(
    Pedido,
    DetallePedido,
    form=DetallePedidoModelForm,
    extra=1,
    can_delete=True,
    fk_name='pedido'
)


class PromocionAplicadaForm(forms.ModelForm):
    class Meta:
        model = PromocionAplicada
        fields = ['pedido', 'promocion', 'escala_aplicada', 'descripcion_beneficios_obtenidos', 'monto_descuento_generado']