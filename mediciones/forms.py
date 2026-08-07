from django import forms
from django.contrib.auth.models import User
from .models import PlanillaMedicion, Cliente, Articulo, Proceso, Elemento, Control, Maquina, Instrumento, Profile

class UserForm(forms.ModelForm):
    role = forms.ChoiceField(choices=Profile.ROLE_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), required=False, help_text="Dejar en blanco para no cambiar la contraseña")
    
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            try:
                self.fields['role'].initial = self.instance.profile.role
            except Profile.DoesNotExist:
                pass

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get('password'):
            user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
            profile, created = Profile.objects.get_or_create(user=user)
            profile.role = self.cleaned_data.get('role')
            profile.save()
        return user

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
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del Cliente / Razón Social'}),
        }

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

class MaquinaForm(forms.ModelForm):
    class Meta:
        model = Maquina
        fields = ['nombre', 'codigo', 'descripcion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class InstrumentoForm(forms.ModelForm):
    class Meta:
        model = Instrumento
        fields = [
            'nombre', 'codigo', 'tipo', 'marca', 'rango', 'modelo', 'serie', 'ubicacion', 
            'es_propio', 'cliente', 'ultima_calibracion', 'frecuencia_meses', 
            'proxima_calibracion', 'alerta_dias', 'certificado_nro', 'en_servicio', 'es_obsoleto'
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'marca': forms.TextInput(attrs={'class': 'form-control'}),
            'rango': forms.TextInput(attrs={'class': 'form-control'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control'}),
            'serie': forms.TextInput(attrs={'class': 'form-control'}),
            'ubicacion': forms.TextInput(attrs={'class': 'form-control'}),
            'es_propio': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'cliente': forms.Select(attrs={'class': 'form-select'}),
            'ultima_calibracion': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'frecuencia_meses': forms.NumberInput(attrs={'class': 'form-control'}),
            'proxima_calibracion': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'alerta_dias': forms.NumberInput(attrs={'class': 'form-control'}),
            'certificado_nro': forms.TextInput(attrs={'class': 'form-control'}),
            'en_servicio': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'es_obsoleto': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

from .models import HistorialCalibracion

class HistorialCalibracionForm(forms.ModelForm):
    class Meta:
        model = HistorialCalibracion
        fields = ['fecha_calibracion', 'resultado', 'certificado_nro', 'archivo_certificado', 'observaciones']
        widgets = {
            'fecha_calibracion': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'resultado': forms.Select(attrs={'class': 'form-select'}),
            'certificado_nro': forms.TextInput(attrs={'class': 'form-control'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

import re

class OperarioCreationForm(forms.Form):
    legajo = forms.CharField(max_length=20, label="Legajo (Usuario)", widget=forms.TextInput(attrs={'class': 'form-control'}))
    nombre = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'class': 'form-control'}))
    apellido = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'class': 'form-control'}))
    pin = forms.CharField(max_length=4, label="PIN (Contraseña)", widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    pin_confirmacion = forms.CharField(max_length=4, label="Confirmar PIN", widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    def clean(self):
        cleaned_data = super().clean()
        pin = cleaned_data.get('pin')
        pin_conf = cleaned_data.get('pin_confirmacion')

        if pin and pin_conf:
            if not re.match(r'^\d{4}$', pin):
                self.add_error('pin', 'El PIN debe contener exactamente 4 números.')
            if pin != pin_conf:
                self.add_error('pin_confirmacion', 'Los PINs no coinciden.')
        return cleaned_data

class OperarioEditForm(forms.Form):
    nombre = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'class': 'form-control'}))
    apellido = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'class': 'form-control'}))
    pin = forms.CharField(max_length=4, required=False, label="Nuevo PIN (Opcional)", widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    pin_confirmacion = forms.CharField(max_length=4, required=False, label="Confirmar Nuevo PIN", widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    def clean(self):
        cleaned_data = super().clean()
        pin = cleaned_data.get('pin')
        pin_conf = cleaned_data.get('pin_confirmacion')

        if pin or pin_conf:
            if not re.match(r'^\d{4}$', pin):
                self.add_error('pin', 'El nuevo PIN debe contener exactamente 4 números.')
            if pin != pin_conf:
                self.add_error('pin_confirmacion', 'Los PINs no coinciden.')
        return cleaned_data
