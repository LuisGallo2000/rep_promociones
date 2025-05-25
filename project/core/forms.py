from django import forms
from .models import Promocion, CondicionPromocion, BeneficioPromocion, EscalaPromocion

class PromocionForm(forms.ModelForm):
    class Meta:
        model = Promocion
        fields = '__all__'
        widgets = {
            'fecha_inicio': forms.DateInput(attrs={'type': 'date'}),
            'fecha_fin': forms.DateInput(attrs={'type': 'date'}),
        }

class CondicionPromocionForm(forms.ModelForm):
    class Meta:
        model = CondicionPromocion
        fields = '__all__'

class BeneficioPromocionForm(forms.ModelForm):
    class Meta:
        model = BeneficioPromocion
        fields = '__all__'

class EscalaPromocionForm(forms.ModelForm):
    class Meta:
        model = EscalaPromocion
        fields = '__all__'