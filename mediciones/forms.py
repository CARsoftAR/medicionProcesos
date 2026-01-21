from django import forms
from .models import PlanillaMedicion, Cliente, Articulo, Proceso, Elemento, Control

class PlanillaForm(forms.ModelForm):
    class Meta:
        model = PlanillaMedicion
        fields = ['cliente', 'proyecto', 'num_op', 'articulo', 'proceso', 'elemento']
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-select select2-enable'}),
            'proyecto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 25-028'}),
            'num_op': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 45806'}),
            'articulo': forms.Select(attrs={'class': 'form-select select2-enable'}),
            'proceso': forms.Select(attrs={'class': 'form-select select2-enable'}),
            'elemento': forms.Select(attrs={'class': 'form-select select2-enable'}),
        }

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombre']

class ArticuloForm(forms.ModelForm):
    class Meta:
        model = Articulo
        fields = ['nombre']

class ProcesoForm(forms.ModelForm):
    class Meta:
        model = Proceso
        fields = ['nombre', 'descripcion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Torneado, Fresado, etc.'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Detalles adicionales...'}),
        }

class ElementoForm(forms.ModelForm):
    class Meta:
        model = Elemento
        fields = ['nombre']

class ControlForm(forms.ModelForm):
    class Meta:
        model = Control
        fields = ['nombre', 'pnp']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Diámetro Exterior, Longitud, Pasa/No Pasa'}),
            'pnp': forms.CheckboxInput(attrs={'class': 'form-check-input', 'style': 'width: 1.25em; height: 1.25em;'}),
        }

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre')
        if nombre:
            # Check for duplicates, excluding the current instance if editing
            qs = Control.objects.filter(nombre__iexact=nombre)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            
            if qs.exists():
                raise forms.ValidationError(f'Ya existe un control con el nombre "{nombre}".')
        return nombre
