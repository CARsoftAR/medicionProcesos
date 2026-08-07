import os

base_path = r'c:\Sistemas ABBAMAT\medicionProcesos\mediciones'

models_code = """
class Operario(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='operario')
    activo = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        db_table = 'OPERARIOS'
        verbose_name = 'Operario'
        verbose_name_plural = 'Operarios'

    def __str__(self):
        return f"{self.user.username} - {self.user.first_name} {self.user.last_name}"
"""

with open(os.path.join(base_path, 'models.py'), 'a', encoding='utf-8') as f:
    f.write(models_code)

forms_code = """
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
            if not re.match(r'^\\d{4}$', pin):
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
            if not re.match(r'^\\d{4}$', pin):
                self.add_error('pin', 'El nuevo PIN debe contener exactamente 4 números.')
            if pin != pin_conf:
                self.add_error('pin_confirmacion', 'Los PINs no coinciden.')
        return cleaned_data
"""

with open(os.path.join(base_path, 'forms.py'), 'a', encoding='utf-8') as f:
    f.write(forms_code)

views_code = """
from .models import Operario
from .forms import OperarioCreationForm, OperarioEditForm
from django.shortcuts import get_object_or_404

def is_admin(user):
    return user.is_superuser or user.is_staff

@user_passes_test(is_admin)
def lista_operarios(request):
    operarios = Operario.objects.filter(activo=True).select_related('user')
    return render(request, 'mediciones/operarios_list.html', {'operarios': operarios})

@user_passes_test(is_admin)
def alta_operario(request):
    if request.method == 'POST':
        form = OperarioCreationForm(request.POST)
        if form.is_valid():
            legajo = form.cleaned_data['legajo']
            
            if User.objects.filter(username=legajo).exists():
                messages.error(request, 'El legajo ya se encuentra registrado en el sistema.')
            else:
                user = User.objects.create_user(
                    username=legajo,
                    first_name=form.cleaned_data['nombre'],
                    last_name=form.cleaned_data['apellido'],
                    password=form.cleaned_data['pin']
                )
                Operario.objects.create(user=user)
                messages.success(request, f'Operario {legajo} registrado con éxito.')
                return redirect('lista_operarios')
    else:
        form = OperarioCreationForm()

    return render(request, 'mediciones/operario_form.html', {'form': form, 'titulo': 'Alta Operario'})

@user_passes_test(is_admin)
def editar_operario(request, id):
    operario = get_object_or_404(Operario, id=id, activo=True)
    user = operario.user

    if request.method == 'POST':
        form = OperarioEditForm(request.POST)
        if form.is_valid():
            user.first_name = form.cleaned_data['nombre']
            user.last_name = form.cleaned_data['apellido']
            
            nuevo_pin = form.cleaned_data.get('pin')
            if nuevo_pin:
                user.set_password(nuevo_pin)
                
            user.save()
            messages.success(request, f'Operario {user.username} actualizado correctamente.')
            return redirect('lista_operarios')
    else:
        form = OperarioEditForm(initial={
            'nombre': user.first_name,
            'apellido': user.last_name
        })

    return render(request, 'mediciones/operario_form.html', {'form': form, 'operario': operario, 'titulo': 'Editar Operario'})

@user_passes_test(is_admin)
def eliminar_operario(request, id):
    operario = get_object_or_404(Operario, id=id)
    if request.method == 'POST':
        operario.activo = False
        operario.save()
        
        user = operario.user
        user.is_active = False
        user.save()
        
        messages.success(request, f'El operario {user.username} ha sido dado de baja del sistema.')
        return redirect('lista_operarios')
        
    return render(request, 'mediciones/operarios_list.html')
"""

with open(os.path.join(base_path, 'views.py'), 'a', encoding='utf-8') as f:
    f.write(views_code)

print("Done appending to models, forms, and views.")
