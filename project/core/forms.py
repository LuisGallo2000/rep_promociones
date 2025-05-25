from django import forms
from .models import Articulo, GrupoProveedor, Linea, Promocion, CondicionPromocion, BeneficioPromocion, EscalaPromocion

class PromocionForm(forms.ModelForm):
    class Meta:
        model = Promocion
        fields = '__all__'
        widgets = {
            'fecha_inicio': forms.DateInput(attrs={'type': 'date'}),
            'fecha_fin': forms.DateInput(attrs={'type': 'date'}),
        }

class CondicionPromocionForm(forms.ModelForm):
    articulo_nombre = forms.CharField(required=False, label='Artículo')
    linea_nombre = forms.CharField(required=False, label='Línea')
    grupo_nombre = forms.CharField(required=False, label='Grupo Proveedor')

    class Meta:
        model = CondicionPromocion
        fields = [
            'cantidad_minima', 'monto_minimo', 
            'cantidad_maxima', 'monto_maximo', 'obligatoria',
            'articulo', 'linea', 'grupo'  # necesarios aunque se oculten
        ]
        widgets = {
            'articulo': forms.HiddenInput(),
            'linea': forms.HiddenInput(),
            'grupo': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Precargar nombres si el formulario tiene una instancia
        if self.instance and self.instance.pk:
            if self.instance.articulo:
                self.fields['articulo_nombre'].initial = self.instance.articulo.nombre
            if self.instance.linea:
                self.fields['linea_nombre'].initial = self.instance.linea.nombre
            if self.instance.grupo:
                self.fields['grupo_nombre'].initial = self.instance.grupo.nombre

class BeneficioPromocionForm(forms.ModelForm):
    class Meta:
        model = BeneficioPromocion
        fields = '__all__'

class EscalaPromocionForm(forms.ModelForm):
    class Meta:
        model = EscalaPromocion
        fields = '__all__'