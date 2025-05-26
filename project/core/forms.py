from django import forms
from django.forms import inlineformset_factory # BaseInlineFormSet no es necesario importarlo directamente aquí usualmente
from .models import (
    Empresa, Sucursal, CanalCliente, GrupoProveedor, Linea, Articulo,
    Vendedor, Cliente, Promocion, CondicionPromocion, EscalaPromocion,
    BeneficioPromocion, Pedido, DetallePedido, PromocionAplicada
)

class CondicionPromocionModelForm(forms.ModelForm):
    # Campos para búsqueda con autocompletar
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
        # 'promocion' y 'condicionpromocion_id' son excluidos
        # Los campos de FK reales se vuelven hidden
        fields = [
            'articulo', 'linea', 'grupo', 
            'cantidad_minima', 'monto_minimo', 'obligatoria_en_conjunto',
            'articulo_search', 'linea_search', 'grupo_search' # Añadir los campos de búsqueda
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
        # Si hay una instancia (editando), poblar los campos de búsqueda con la descripción actual
        if self.instance and self.instance.pk:
            if self.instance.articulo:
                self.initial['articulo_search'] = f"E:{self.instance.articulo.empresa.empresa_id} | {self.instance.articulo.codigo_articulo} - {self.instance.articulo.descripcion}"
            if self.instance.linea:
                self.initial['linea_search'] = self.instance.linea.nombre
            if self.instance.grupo:
                self.initial['grupo_search'] = self.instance.grupo.nombre
        
        # Asegurarse que los campos FK no sean requeridos si el campo de búsqueda correspondiente se usa
        self.fields['articulo'].required = False
        self.fields['linea'].required = False
        self.fields['grupo'].required = False

    def clean(self):
        cleaned_data = super().clean()
        # Si un campo de búsqueda tiene valor pero el campo FK no (porque JS falló o no se seleccionó),
        # podríamos intentar buscar el objeto aquí o simplemente confiar en que el JS ponga el ID.
        # Por ahora, asumimos que el JS rellena el campo FK (articulo, linea, grupo).
        
        # Lógica para asegurar que solo uno de articulo, linea o grupo esté seleccionado para una condición:
        selected_targets = 0
        if cleaned_data.get('articulo'): selected_targets += 1
        if cleaned_data.get('linea'): selected_targets += 1
        if cleaned_data.get('grupo'): selected_targets += 1

        if selected_targets > 1:
            raise forms.ValidationError("Por favor, seleccione solo un Artículo, o una Línea, o un Grupo para la condición, no múltiples.")
        # Si no se selecciona ninguno Y la condición requiere un target (ej. no es promo total_pedido), se podría añadir error.
        # Esto depende de la lógica de 'aplica_por' de la Promocion padre.
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
        
        self.fields['articulo_bonificado'].required = False # El campo FK se vuelve no requerido
        self.fields['cantidad_bonificada'].required = False
        self.fields['porcentaje_descuento'].required = False

    def clean(self):
        cleaned_data = super().clean()
        tipo = cleaned_data.get("tipo")

        if tipo == "bonificacion":
            # El ID del artículo bonificado debería estar en cleaned_data['articulo_bonificado']
            # si el JS lo puso correctamente en el hidden input.
            if not cleaned_data.get("articulo_bonificado"):
                # Si el campo de búsqueda tiene texto pero el ID no se seteó, podría ser un error
                if cleaned_data.get("articulo_bonificado_search"):
                     self.add_error('articulo_bonificado_search', 'Debe seleccionar un artículo válido de la lista.')
                else: # Si ni el campo de búsqueda ni el ID tienen valor
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
        fields = [ # Especificar campos para excluir los IDs autogenerados si no son UUIDField definidos explícitamente
            'empresa', 'codigo_articulo', 'codigo_barras', 'codigo_ean',
            'descripcion', 'grupo', 'linea', 'unidad_medida', 'unidad_compra',
            'unidad_reparto', 'unidad_bonificacion', 'factor_reparto',
            'factor_compra', 'factor_bonificacion', 'tipo_afectacion', 'peso',
            'tipo_producto', 'afecto_retencion', 'afecto_detraccion'
        ]
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            # 'fecha_creacion' no existe en tu modelo Articulo, lo quito
            # Añade más widgets según necesites para los otros campos
            'empresa': forms.Select(attrs={'class': 'form-select'}),
            'codigo_articulo': forms.TextInput(attrs={'class': 'form-control'}),
            'grupo': forms.Select(attrs={'class': 'form-select'}),
            'linea': forms.Select(attrs={'class': 'form-select'}),
            # ... y así para los demás campos que quieras estilizar
        }

class VendedorForm(forms.ModelForm):
    class Meta:
        model = Vendedor
        fields = [
            'nro_documento', 'tipo_identificacion_id', 'nombres', 'direccion',
            'nro_movil', 'canal', 'supervisor', 'correo_electronico', 'territorio', 'rol_id'
        ]
        # Añade widgets si es necesario

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombres', 'canal', 'nro_documento', 'tipo_documento', 'tipo_cliente']
        # Añade widgets si es necesario


# === FORMULARIOS DE PROMOCIONES Y SUS ELEMENTOS ANIDADOS ===

class PromocionModelForm(forms.ModelForm): # Este es el que debes usar
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
    # Beneficio 1
    beneficio1_tipo = forms.ChoiceField(
        choices=[('', '---------')] + BeneficioPromocion.TIPO_BENEFICIO_CHOICES, 
        required=False, 
        label="Tipo Beneficio 1", 
        widget=forms.Select(attrs={'class': 'form-select beneficio-tipo-escala', 'data-beneficio-idx': '1'})
    )
    beneficio1_articulo_search = forms.CharField(
        label='Buscar Artículo Bonificado 1', 
        required=False, 
        widget=forms.TextInput(attrs={'class': 'form-control articulo-bonificado-search-input', 'data-beneficio-idx': '1', 'placeholder': 'Escriba para buscar...'})
    )
    beneficio1_articulo_bonificado = forms.ModelChoiceField(
        queryset=Articulo.objects.all(), # Queryset base para validación
        required=False, 
        widget=forms.HiddenInput(attrs={'class': 'articulo-bonificado-pk-input', 'data-beneficio-idx': '1'}),
        to_field_name="articulo_id" # Coincide con el PK de Articulo
    )
    beneficio1_cantidad_bonificada = forms.IntegerField(
        required=False, 
        label="Cantidad Bonificada 1", 
        widget=forms.NumberInput(attrs={'class': 'form-control', 'data-beneficio-idx': '1', 'min': '1'})
    )
    beneficio1_porcentaje_descuento = forms.DecimalField(
        required=False, 
        label="Porcentaje Descuento 1 (%)", 
        max_digits=5, decimal_places=2, 
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'data-beneficio-idx': '1', 'min': '0', 'max': '100'})
    )

    # Beneficio 2
    beneficio2_tipo = forms.ChoiceField(
        choices=[('', '---------')] + BeneficioPromocion.TIPO_BENEFICIO_CHOICES, 
        required=False, 
        label="Tipo Beneficio 2", 
        widget=forms.Select(attrs={'class': 'form-select beneficio-tipo-escala', 'data-beneficio-idx': '2'})
    )
    beneficio2_articulo_search = forms.CharField(
        label='Buscar Artículo Bonificado 2', 
        required=False, 
        widget=forms.TextInput(attrs={'class': 'form-control articulo-bonificado-search-input', 'data-beneficio-idx': '2', 'placeholder': 'Escriba para buscar...'})
    )
    beneficio2_articulo_bonificado = forms.ModelChoiceField(
        queryset=Articulo.objects.all(), 
        required=False, 
        widget=forms.HiddenInput(attrs={'class': 'articulo-bonificado-pk-input', 'data-beneficio-idx': '2'}),
        to_field_name="articulo_id"
    )
    beneficio2_cantidad_bonificada = forms.IntegerField(
        required=False, 
        label="Cantidad Bonificada 2", 
        widget=forms.NumberInput(attrs={'class': 'form-control', 'data-beneficio-idx': '2', 'min': '1'})
    )
    beneficio2_porcentaje_descuento = forms.DecimalField(
        required=False, 
        label="Porcentaje Descuento 2 (%)", 
        max_digits=5, decimal_places=2, 
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'data-beneficio-idx': '2', 'min': '0', 'max': '100'})
    )

    class Meta:
        model = EscalaPromocion
        exclude = ['promocion', 'escalapromocion_id']
        fields = [
            'descripcion_escala', 'desde_monto', 'hasta_monto', 
            'desde_cantidad', 'hasta_cantidad', 'proporcional',
            'base_cantidad_proporcional_escala', 'base_monto_proporcional_escala',
            'beneficio1_tipo', 'beneficio1_articulo_search', 'beneficio1_articulo_bonificado',
            'beneficio1_cantidad_bonificada', 'beneficio1_porcentaje_descuento',
            'beneficio2_tipo', 'beneficio2_articulo_search', 'beneficio2_articulo_bonificado',
            'beneficio2_cantidad_bonificada', 'beneficio2_porcentaje_descuento',
        ]
        widgets = {
            'descripcion_escala': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: De 10 a 20 unidades'}),
            'desde_monto': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'hasta_monto': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'desde_cantidad': forms.NumberInput(attrs={'class': 'form-control'}),
            'hasta_cantidad': forms.NumberInput(attrs={'class': 'form-control'}),
            'proporcional': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'base_cantidad_proporcional_escala': forms.NumberInput(attrs={'class': 'form-control'}),
            'base_monto_proporcional_escala': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            beneficios = list(self.instance.beneficios.all().order_by('beneficiopromocion_id')[:2]) # Ordenar para consistencia
            if len(beneficios) > 0: self._populate_beneficio_fields_initial(beneficios[0], '1')
            if len(beneficios) > 1: self._populate_beneficio_fields_initial(beneficios[1], '2')
        
    def _populate_beneficio_fields_initial(self, beneficio_instance, index_str):
        self.initial[f'beneficio{index_str}_tipo'] = beneficio_instance.tipo
        if beneficio_instance.articulo_bonificado:
            self.initial[f'beneficio{index_str}_articulo_bonificado'] = beneficio_instance.articulo_bonificado_id # Usar el ID para initial de ModelChoiceField
            self.initial[f'beneficio{index_str}_articulo_search'] = f"E:{beneficio_instance.articulo_bonificado.empresa.empresa_id} | {beneficio_instance.articulo_bonificado.codigo_articulo} - {beneficio_instance.articulo_bonificado.descripcion}"
        self.initial[f'beneficio{index_str}_cantidad_bonificada'] = beneficio_instance.cantidad_bonificada
        self.initial[f'beneficio{index_str}_porcentaje_descuento'] = beneficio_instance.porcentaje_descuento

    def _clean_beneficio_fields(self, cleaned_data, index_str):
        tipo = cleaned_data.get(f'beneficio{index_str}_tipo')
        # El ModelChoiceField ya habrá intentado convertir el ID a una instancia
        articulo_instancia = cleaned_data.get(f'beneficio{index_str}_articulo_bonificado')
        cantidad = cleaned_data.get(f'beneficio{index_str}_cantidad_bonificada')
        porcentaje = cleaned_data.get(f'beneficio{index_str}_porcentaje_descuento')
        articulo_search_text = cleaned_data.get(f'beneficio{index_str}_articulo_search')

        if tipo == 'bonificacion':
            if not articulo_instancia:
                # Si el campo de búsqueda tiene texto pero no se resolvió a una instancia, es un error de selección.
                # Si el ModelChoiceField ya dio error porque el ID no existe, ese error se mostrará.
                # Este error es más para el caso en que el usuario no seleccionó nada pero el tipo es bonif.
                if not self.errors.get(f'beneficio{index_str}_articulo_bonificado'): # Solo añadir si ModelChoiceField no dio error ya
                    self.add_error(f'beneficio{index_str}_articulo_search', 'Artículo bonificado es requerido y debe ser válido.')
            if cantidad is None or cantidad <= 0: # Cantidad debe ser positiva
                self.add_error(f'beneficio{index_str}_cantidad_bonificada', 'Cantidad debe ser un número positivo para bonificación.')
            cleaned_data[f'beneficio{index_str}_porcentaje_descuento'] = None
        elif tipo == 'descuento':
            if porcentaje is None or porcentaje <= 0: # Porcentaje debe ser positivo
                self.add_error(f'beneficio{index_str}_porcentaje_descuento', 'Porcentaje de descuento debe ser un número positivo.')
            cleaned_data[f'beneficio{index_str}_articulo_bonificado'] = None
            cleaned_data[f'beneficio{index_str}_cantidad_bonificada'] = None
            cleaned_data[f'beneficio{index_str}_articulo_search'] = ''
        elif not tipo or tipo == '': # No se seleccionó tipo, limpiar todos los campos de este beneficio
            cleaned_data[f'beneficio{index_str}_articulo_bonificado'] = None
            cleaned_data[f'beneficio{index_str}_cantidad_bonificada'] = None
            cleaned_data[f'beneficio{index_str}_porcentaje_descuento'] = None
            cleaned_data[f'beneficio{index_str}_articulo_search'] = ''
    
    def clean(self):
        cleaned_data = super().clean()
        self._clean_beneficio_fields(cleaned_data, '1')
        self._clean_beneficio_fields(cleaned_data, '2')
        return cleaned_data

    def save(self, commit=True):
        escala_instance = super().save(commit=False) 
        # El `promocion` FK se asigna por el formset.instance
        
        if commit:
            escala_instance.save() 
            self.save_beneficios(escala_instance) 
        # Si commit=False, el formset padre (EscalaPromocionFormSet) necesitará una forma
        # de llamar a save_beneficios después de que todo se guarde, o la vista lo hace.
        # Con la lógica de vista actual, este save() con commit=True llamado por el formset.save() es suficiente.
        return escala_instance

    def save_beneficios(self, escala_instance):
        # Este método es llamado por el save() de este form, después de que escala_instance tiene PK.
        escala_instance.beneficios.all().delete() 

        for index_str in ['1', '2']:
            beneficio_tipo = self.cleaned_data.get(f'beneficio{index_str}_tipo')
            if beneficio_tipo:
                articulo_bonif_instancia = self.cleaned_data.get(f'beneficio{index_str}_articulo_bonificado')
                
                if beneficio_tipo == 'bonificacion' and not articulo_bonif_instancia:
                    continue 

                BeneficioPromocion.objects.create(
                    escala=escala_instance,
                    # promocion=None, # No es un beneficio directo de la promoción
                    tipo=beneficio_tipo,
                    articulo_bonificado=articulo_bonif_instancia,
                    cantidad_bonificada=self.cleaned_data.get(f'beneficio{index_str}_cantidad_bonificada'),
                    porcentaje_descuento=self.cleaned_data.get(f'beneficio{index_str}_porcentaje_descuento')
                )

# El EscalaPromocionFormSet usará este EscalaPromocionModelForm
EscalaPromocionFormSet = inlineformset_factory(
    Promocion,
    EscalaPromocion,
    form=EscalaPromocionModelForm, # Usar el form modificado
    extra=1,
    can_delete=True,
    fk_name='promocion'
)


# Formsets para gestionar elementos anidados de Promocion
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
        # Generalmente no se edita, es más para visualización.