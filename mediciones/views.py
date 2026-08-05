from django.shortcuts import render, redirect, get_object_or_404
from django.db import models
from django.core.paginator import Paginator
from django.contrib.auth.models import User
from django.urls import reverse
from django.contrib import messages
from django.http import JsonResponse
from .models import PlanillaMedicion, Cliente, Articulo, Proceso, Elemento, Control, Tolerancia, ValorMedicion, Maquina, Instrumento, Profile, HistorialCalibracion
from .forms import PlanillaForm, ClienteForm, ArticuloForm, ProcesoForm, ElementoForm, ControlForm, UserForm, InstrumentoForm, MaquinaForm
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.template.loader import get_template
from xhtml2pdf import pisa
from django.http import HttpResponse
from django.utils import timezone
from django.core.files.storage import FileSystemStorage
import datetime
import re
import os
import json
import time

# CONEXIÓN CORREGIDA: Motor OCR 100% Local sin IA
from .lector_local import extraer_datos_de_pdf

import os
import cv2
import fitz
import base64
import numpy as np
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

import pytesseract

# Autoconfiguración de Tesseract

def abrir_archivo_seguro(ruta, intentos=5):
    """
    Abre un archivo con reintentos para evitar WinError 32 (archivo bloqueado por el SO).
    Espera 0.5s entre cada intento para que Windows libere el handle del archivo.
    """
    for i in range(intentos):
        try:
            with open(ruta, 'rb') as f:
                return f.read()
        except PermissionError:
            if i < intentos - 1:
                time.sleep(0.5)
    raise IOError(f"No se pudo acceder al archivo después de {intentos} intentos: {ruta}")

def eliminar_archivo_seguro(ruta, intentos=3):
    """Elimina un archivo con reintentos para evitar WinError 32 en cleanup."""
    for i in range(intentos):
        try:
            if os.path.exists(ruta):
                os.remove(ruta)
            return
        except PermissionError:
            if i < intentos - 1:
                time.sleep(0.5)

@csrf_exempt
def api_procesar_planilla(request):
    """
    Endpoint Django para la extracción por IA pura.
    Recibe el PDF del frontend y devuelve el JSON de Gemini sin pasar por OCR local.
    """
    if request.method == 'POST' and request.FILES.get('plano_pdf'):
        pdf_file = request.FILES['plano_pdf']
        
        from django.core.files.storage import FileSystemStorage
        import os
        fs = FileSystemStorage(location=os.path.join('media', 'temporales'))
        filename = fs.save(pdf_file.name, pdf_file)
        uploaded_file_path = fs.path(filename)
        
        try:
            # Obtener API key del usuario si existe
            from .models import Profile
            gemini_key = None
            if request.user.is_authenticated:
                try:
                    profile = request.user.profile
                    gemini_key = profile.gemini_api_key
                except Profile.DoesNotExist:
                    pass
            
            # Leer con reintentos para evitar WinError 32 (archivo bloqueado por Windows)
            pdf_bytes = abrir_archivo_seguro(uploaded_file_path)

            # IA como único motor de procesamiento
            datos_ia = extraer_datos_de_pdf(
                pdf_bytes=pdf_bytes,
                api_key=gemini_key or None
            )
            
            if not isinstance(datos_ia, dict):
                raise ValueError("La API devolvió una respuesta vacía o un formato JSON incompatible.")
                
            return JsonResponse({
                "status": "success",
                "datos_ia": datos_ia
            })
            
        except Exception as e:
            return JsonResponse({
                "status": "error", 
                "message": f"Fallo de IA. No se completará con datos falsos. Detalles: {str(e)}"
            }, status=400)
        finally:
            eliminar_archivo_seguro(uploaded_file_path)
                
    return JsonResponse({"status": "error", "message": "No se envió ningún archivo plano_pdf."}, status=400)


def supervisor_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role == 'CALIDAD'):
            return view_func(request, *args, **kwargs)
        messages.error(request, "Acceso denegado: Se requieren permisos de Supervisor/Calidad.")
        return redirect('index')
    return _wrapped_view

def login_view(request):
    if request.user.is_authenticated:
        next_url = request.GET.get('next')
        if next_url:
            return redirect(next_url)
        return redirect('index')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('index')
        else:
            messages.error(request, "Usuario o contraseña incorrectos.")
    else:
        form = AuthenticationForm()
    return render(request, 'mediciones/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def perfil_usuario(request):
    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=request.user)
        if user_form.is_valid():
            user_form.save()
            messages.success(request, 'Perfil actualizado correctamente.')
            return redirect('perfil_usuario')
    else:
        user_form = UserForm(instance=request.user)
        if not (request.user.is_superuser or request.user.profile.role == 'CALIDAD'):
            user_form.fields['role'].disabled = True
    return render(request, 'mediciones/perfil.html', {'user_form': user_form})

@supervisor_required
def lista_usuarios(request):
    usuarios = User.objects.all().select_related('profile').order_by('username')
    return render(request, 'mediciones/usuarios_lista.html', {'usuarios': usuarios})

@supervisor_required
def crear_usuario(request):
    if request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Usuario creado correctamente.')
            return redirect('lista_usuarios')
    else:
        form = UserForm()
        form.fields['password'].required = True
        form.fields['password'].help_text = "Ingrese la contraseña inicial"
    return render(request, 'mediciones/usuario_form.html', {'form': form, 'titulo': 'Nuevo Usuario'})

@supervisor_required
def editar_usuario(request, user_id):
    user_to_edit = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        form = UserForm(request.POST, instance=user_to_edit)
        if form.is_valid():
            form.save()
            messages.success(request, 'Usuario actualizado correctamente.')
            return redirect('lista_usuarios')
    else:
        form = UserForm(instance=user_to_edit)
    return render(request, 'mediciones/usuario_form.html', {'form': form, 'titulo': 'Editar Usuario', 'is_edit': True})

@supervisor_required
def eliminar_usuario(request, user_id):
    user_to_delete = get_object_or_404(User, id=user_id)
    if user_to_delete == request.user:
        messages.error(request, 'No puedes eliminarte a ti mismo.')
    elif user_to_delete.is_superuser and not request.user.is_superuser:
         messages.error(request, 'No tienes permisos para eliminar a un superusuario.')
    else:
        user_to_delete.delete()
        messages.success(request, 'Usuario eliminado correctamente.')
    return redirect('lista_usuarios')

@login_required
def index(request):
    from django.db.models import Count, Q
    from django.utils import timezone
    from datetime import timedelta
    
    q = request.GET.get('q', '').strip()
    planillas_qs = PlanillaMedicion.objects.all().order_by('-id')
    valores_qs = ValorMedicion.objects.all()
    
    is_filtered = False
    if q:
        planillas_qs = planillas_qs.filter(
            Q(num_op__icontains=q) | 
            Q(proyecto__icontains=q) |
            Q(cliente__nombre__icontains=q) |
            Q(articulo__nombre__icontains=q)
        )
        valores_qs = valores_qs.filter(
            Q(op__icontains=q) | 
            Q(planilla__proyecto__icontains=q)
        )
        is_filtered = True

    limit = 15 if not q else 50
    planillas = planillas_qs[:limit]
    
    hoy = timezone.now()
    hace_30_dias = hoy - timedelta(days=30)
    total_ops = planillas_qs.count()
    
    if is_filtered:
        mediciones_base = valores_qs
    else:
        mediciones_base = valores_qs.filter(fecha__gte=hace_30_dias)

    mediciones_recientes = mediciones_base.count()
    ok_count = mediciones_base.filter(valor_pnp='OK').count()
    nok_count = mediciones_base.filter(valor_pnp='NOK').count()
    
    dias = []
    mediciones_por_dia = []
    oks_por_dia = []
    
    for i in range(6, -1, -1):
        fecha = hoy - timedelta(days=i)
        dias.append(fecha.strftime('%d/%m'))
        count = valores_qs.filter(fecha__date=fecha.date()).count()
        oks = valores_qs.filter(fecha__date=fecha.date(), valor_pnp='OK').count()
        mediciones_por_dia.append(count)
        oks_por_dia.append(oks)

    instrumentos_activos = Instrumento.objects.filter(es_obsoleto=False)
    inst_vencidos = [i for i in instrumentos_activos if i.is_calibracion_vencida()]
    inst_alerta = [i for i in instrumentos_activos if i.is_en_alerta()]

    context = {
        'planillas': planillas,
        'total_ops': total_ops,
        'mediciones_recientes': mediciones_recientes,
        'ok_count': ok_count,
        'nok_count': nok_count,
        'stats_dias': dias,
        'stats_mediciones': mediciones_por_dia,
        'stats_oks': oks_por_dia,
        'inst_vencidos_count': len(inst_vencidos),
        'inst_alerta_count': len(inst_alerta),
        'total_vencidos_alerta': len(inst_vencidos) + len(inst_alerta),
        'is_filtered': is_filtered,
        'search_query': q
    }

    if request.GET.get('partial') == '1' or request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'mediciones/partials/dashboard_table.html', context)
    return render(request, 'mediciones/dashboard.html', context)

@login_required
def asignar_op(request):
    if request.method == 'POST':
        form = PlanillaForm(request.POST)
        if form.is_valid():
            planilla = form.save()
            messages.success(request, f'Planilla para OP {planilla.num_op} iniciada correctamente.')
            return redirect('crear_procesos', planilla_id=planilla.id)
    else:
        form = PlanillaForm()
    
    cliente_form = ClienteForm()
    articulo_form = ArticuloForm()
    proceso_form = ProcesoForm()
    elemento_form = ElementoForm()
    
    context = {
        'form': form,
        'cliente_form': cliente_form,
        'articulo_form': articulo_form,
        'proceso_form': proceso_form,
        'elemento_form': elemento_form,
    }
    return render(request, 'mediciones/asignar_op.html', context)

@supervisor_required
def crear_procesos(request, planilla_id):
    planilla = get_object_or_404(PlanillaMedicion, id=planilla_id)
    if request.method == 'POST':
        selected_controls = request.POST.getlist('controles')
        if selected_controls:
            current_count = Tolerancia.objects.filter(planilla=planilla).count()
            for index, control_id in enumerate(selected_controls):
                control = Control.objects.get(id=control_id)
                Tolerancia.objects.create(
                    planilla=planilla,
                    control=control,
                    posicion=current_count + index + 1
                )
            messages.success(request, 'Controles asignados correctamente.')
            return redirect('asignar_tolerancias', planilla_id=planilla.id)
        else:
            messages.warning(request, 'Debe seleccionar al menos un control.')

    assigned_tolerancias = Tolerancia.objects.filter(planilla=planilla).select_related('control')
    all_controls = Control.objects.all()
    context = {
        'planilla': planilla,
        'assigned': assigned_tolerancias,
        'controls': all_controls
    }
    return render(request, 'mediciones/crear_procesos.html', context)

@supervisor_required
def asignar_tolerancias(request, planilla_id):
    planilla = get_object_or_404(PlanillaMedicion, id=planilla_id)
    tolerancias = Tolerancia.objects.filter(planilla=planilla).select_related('control').order_by('posicion')

    if request.method == 'POST':
        for tolerancia in tolerancias:
            if tolerancia.control.pnp:
                continue
            nom = request.POST.get(f'nominal_{tolerancia.id}')
            min_val = request.POST.get(f'min_{tolerancia.id}')
            max_val = request.POST.get(f'max_{tolerancia.id}')
            if nom: tolerancia.nominal = nom
            if min_val: tolerancia.minimo = min_val
            if max_val: tolerancia.maximo = max_val
            tolerancia.save()
            
        messages.success(request, 'Tolerancias guardadas correctamente.')
        proc_id = planilla.proceso.id if planilla.proceso else ''
        proy = planilla.proyecto if planilla.proyecto else ''
        op = planilla.num_op if planilla.num_op else ''
        return redirect(f"{reverse('nueva_medicion_op')}?proy={proy}&op={op}&proc={proc_id}")

    context = {
        'planilla': planilla,
        'tolerancias': tolerancias
    }
    return render(request, 'mediciones/asignar_tolerancias.html', context)

@login_required
def ingreso_mediciones(request, planilla_id):
    planilla = get_object_or_404(PlanillaMedicion, id=planilla_id)
    proc_id = planilla.proceso.id if planilla.proceso else ''
    proy = planilla.proyecto if planilla.proyecto else ''
    op = planilla.num_op if planilla.num_op else ''
    return redirect(f"{reverse('nueva_medicion_op')}?proy={proy}&op={op}&proc={proc_id}")

@supervisor_required
def api_create_master(request, model_name):
    if request.method == 'POST':
        name = request.POST.get('nombre')
        if not name:
            return JsonResponse({'status': 'error', 'message': 'Nombre es requerido'}, status=400)
        try:
            if model_name == 'cliente': obj = Cliente.objects.create(nombre=name)
            elif model_name == 'articulo': obj = Articulo.objects.create(nombre=name)
            elif model_name == 'proceso': obj = Proceso.objects.create(nombre=name)
            elif model_name == 'elemento': obj = Elemento.objects.create(nombre=name)
            elif model_name == 'control':
                 if Control.objects.filter(nombre__iexact=name).exists():
                     return JsonResponse({'status': 'error', 'message': f'El control "{name}" ya existe.'}, status=400)
                 is_pnp = request.POST.get('pnp') == 'true'
                 obj = Control.objects.create(nombre=name, pnp=is_pnp)
            elif model_name == 'maquina': obj = Maquina.objects.create(nombre=name)
            elif model_name == 'instrumento': obj = Instrumento.objects.create(nombre=name)
            else: return JsonResponse({'status': 'error', 'message': 'Modelo inválido'}, status=400)
            return JsonResponse({'status': 'success', 'id': obj.id, 'nombre': obj.nombre})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

@supervisor_required
def api_delete_tolerancia(request, tolerancia_id):
    if request.method == 'POST':
        try:
            tol = Tolerancia.objects.get(id=tolerancia_id)
            tol.delete()
            return JsonResponse({'status': 'success'})
        except Tolerancia.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)

@login_required
def lista_procesos(request):
    per_page = request.GET.get('per_page')
    if per_page: request.session['procesos_per_page'] = per_page
    else: per_page = request.session.get('procesos_per_page', 10)
    procesos_list = Proceso.objects.all().order_by('nombre')
    paginator = Paginator(procesos_list, per_page)
    page_number = request.GET.get('page')
    procesos = paginator.get_page(page_number)
    return render(request, 'mediciones/lista_procesos.html', {'procesos': procesos, 'per_page': int(per_page)})

@supervisor_required
def crear_proceso(request):
    if request.method == 'POST':
        form = ProcesoForm(request.POST)
        if form.is_valid():
            form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest': return JsonResponse({'status': 'success'})
            messages.success(request, 'Proceso creado correctamente.')
            return redirect('lista_procesos')
    else: form = ProcesoForm()
    return render(request, 'mediciones/crear_proceso.html', {'form': form, 'titulo': 'Nuevo Proceso'})

@supervisor_required
def editar_proceso(request, pk):
    proceso = get_object_or_404(Proceso, pk=pk)
    if request.method == 'POST':
        form = ProcesoForm(request.POST, instance=proceso)
        if form.is_valid():
            form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest': return JsonResponse({'status': 'success', 'edit': True})
            messages.success(request, 'Proceso actualizado correctamente.')
            return redirect('lista_procesos')
    else: form = ProcesoForm(instance=proceso)
    return render(request, 'mediciones/crear_proceso.html', {'form': form, 'titulo': 'Editar Proceso', 'is_edit': True})

@supervisor_required
def eliminar_proceso(request, pk):
    proceso = get_object_or_404(Proceso, pk=pk)
    if request.method == 'POST':
        proceso.delete()
        messages.success(request, 'Proceso eliminado.')
    return redirect('lista_procesos')

@login_required
def lista_clientes(request):
    per_page = request.GET.get('per_page')
    if per_page: request.session['clientes_per_page'] = per_page
    else: per_page = request.session.get('clientes_per_page', 10)
    clientes_list = Cliente.objects.all().order_by('nombre')
    paginator = Paginator(clientes_list, per_page)
    page_number = request.GET.get('page')
    clientes = paginator.get_page(page_number)
    return render(request, 'mediciones/lista_clientes.html', {'clientes': clientes, 'per_page': int(per_page)})

@supervisor_required
def crear_cliente(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cliente creado correctamente.')
            return redirect('lista_clientes')
    else: form = ClienteForm()
    return render(request, 'mediciones/crear_cliente.html', {'form': form, 'titulo': 'Nuevo Cliente'})

@supervisor_required
def editar_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cliente actualizado correctamente.')
            return redirect('lista_clientes')
    else: form = ClienteForm(instance=cliente)
    return render(request, 'mediciones/crear_cliente.html', {'form': form, 'titulo': 'Editar Cliente', 'is_edit': True})

@supervisor_required
def eliminar_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        cliente.delete()
        messages.success(request, 'Cliente eliminado.')
    return redirect('lista_clientes')

@login_required
def lista_elementos(request):
    per_page = request.GET.get('per_page')
    if per_page: request.session['elementos_per_page'] = per_page
    else: per_page = request.session.get('elementos_per_page', 10)
    elementos_list = Elemento.objects.all().order_by('nombre')
    paginator = Paginator(elementos_list, per_page)
    page_number = request.GET.get('page')
    elementos = paginator.get_page(page_number)
    return render(request, 'mediciones/lista_elementos.html', {'elementos': elementos, 'per_page': int(per_page)})

@supervisor_required
def crear_elemento(request):
    if request.method == 'POST':
        form = ElementoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Elemento creado correctamente.')
            return redirect('lista_elementos')
    else: form = ElementoForm()
    return render(request, 'mediciones/crear_elemento.html', {'form': form, 'titulo': 'Nuevo Elemento'})

@supervisor_required
def editar_elemento(request, pk):
    elemento = get_object_or_404(Elemento, pk=pk)
    if request.method == 'POST':
        form = ElementoForm(request.POST, instance=elemento)
        if form.is_valid():
            form.save()
            messages.success(request, 'Elemento actualizado correctamente.')
            return redirect('lista_elementos')
    else: form = ElementoForm(instance=elemento)
    return render(request, 'mediciones/crear_elemento.html', {'form': form, 'titulo': 'Editar Elemento', 'is_edit': True})

@supervisor_required
def eliminar_elemento(request, pk):
    elemento = get_object_or_404(Elemento, pk=pk)
    if request.method == 'POST':
        elemento.delete()
        messages.success(request, 'Elemento eliminado.')
    return redirect('lista_elementos')

@login_required
def lista_controles(request):
    per_page = request.GET.get('per_page')
    if per_page: request.session['controles_per_page'] = per_page
    else: per_page = request.session.get('controles_per_page', 10)
    controles_list = Control.objects.all().order_by('nombre')
    paginator = Paginator(controles_list, per_page)
    page_number = request.GET.get('page')
    controles = paginator.get_page(page_number)
    return render(request, 'mediciones/lista_controles.html', {'controles': controles, 'per_page': int(per_page)})

@supervisor_required
def crear_control(request):
    if request.method == 'POST':
        form = ControlForm(request.POST)
        if form.is_valid():
            form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest': return JsonResponse({'status': 'success'})
            messages.success(request, 'Control creado correctamente.')
            return redirect('lista_controles')
        elif request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            error_msg = next(iter(form.errors.values()))[0]
            return JsonResponse({'status': 'error', 'message': error_msg})
    else: form = ControlForm()
    return render(request, 'mediciones/crear_control.html', {'form': form, 'titulo': 'Nuevo Control'})

@supervisor_required
def editar_control(request, pk):
    control = get_object_or_404(Control, pk=pk)
    if request.method == 'POST':
        form = ControlForm(request.POST, instance=control)
        if form.is_valid():
            form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest': return JsonResponse({'status': 'success', 'edit': True})
            messages.success(request, 'Control actualizado correctamente.')
            return redirect('lista_controles')
        elif request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            error_msg = next(iter(form.errors.values()))[0]
            return JsonResponse({'status': 'error', 'message': error_msg})
    else: form = ControlForm(instance=control)
    return render(request, 'crear_control.html', {'form': form, 'titulo': 'Editar Control', 'is_edit': True})

@supervisor_required
def eliminar_control(request, pk):
    control = get_object_or_404(Control, pk=pk)
    if request.method == 'POST':
        control.delete()
        messages.success(request, 'Control eliminado.')
    return redirect('lista_controles')

@login_required
def lista_instrumentos(request):
    per_page = request.GET.get('per_page')
    if per_page: request.session['instrumentos_per_page'] = per_page
    else: per_page = request.session.get('instrumentos_per_page', 10)
    instrumentos_list = Instrumento.objects.all().order_by('nombre')
    
    search = request.GET.get('search')
    if search:
        instrumentos_list = instrumentos_list.filter(
            models.Q(nombre__icontains=search) | 
            models.Q(codigo__icontains=search) |
            models.Q(marca__icontains=search)
        )
    filter_type = request.GET.get('filter')
    if filter_type == 'alertas':
        ids_vencidos = [i.id for i in instrumentos_list if i.is_calibracion_vencida() or i.is_en_alerta()]
        instrumentos_list = instrumentos_list.filter(id__in=ids_vencidos)

    paginator = Paginator(instrumentos_list, per_page)
    page_number = request.GET.get('page')
    instrumentos = paginator.get_page(page_number)
    return render(request, 'mediciones/lista_instrumentos.html', {'instrumentos': instrumentos, 'per_page': int(per_page), 'search': search})

@supervisor_required
def crear_instrumento(request):
    if request.method == 'POST':
        form = InstrumentoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Instrumento creado correctamente.')
            return redirect('lista_instrumentos')
    else: form = InstrumentoForm()
    return render(request, 'mediciones/crear_instrumento.html', {'form': form, 'titulo': 'Nuevo Instrumento'})

@supervisor_required
def editar_instrumento(request, pk):
    instrumento = get_object_or_404(Instrumento, pk=pk)
    if request.method == 'POST':
        form = InstrumentoForm(request.POST, instance=instrumento)
        if form.is_valid():
            form.save()
            messages.success(request, 'Instrumento actualizado correctamente.')
            return redirect('lista_instrumentos')
    else: form = InstrumentoForm(instance=instrumento)
    return render(request, 'mediciones/crear_instrumento.html', {'form': form, 'titulo': 'Editar Instrumento', 'is_edit': True})

@supervisor_required
def eliminar_instrumento(request, pk):
    instrumento = get_object_or_404(Instrumento, pk=pk)
    if request.method == 'POST':
        instrumento.delete()
        messages.success(request, 'Instrumento eliminado.')
    return redirect('lista_instrumentos')

@supervisor_required
def detalle_instrumento(request, pk):
    instrumento = get_object_or_404(Instrumento, pk=pk)
    historial = instrumento.historial.all().order_by('-fecha_calibracion')
    return render(request, 'mediciones/detalle_instrumento.html', {'instrumento': instrumento, 'historial': historial})

@csrf_exempt
@supervisor_required
def registrar_calibracion_ajax(request):
    if request.method == 'POST':
        from datetime import datetime
        from dateutil.relativedelta import relativedelta
        try:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'multipart/form-data' in request.content_type:
                inst_id = request.POST.get('instrumento_id')
                fecha_str = request.POST.get('fecha')
                resultado = request.POST.get('resultado', 'APROBADO')
                certificado = request.POST.get('certificado', '')
                obs = request.POST.get('observaciones', '')
                archivo = request.FILES.get('archivo_certificado')
            else:
                import json
                data = json.loads(request.body)
                inst_id = data.get('instrumento_id')
                fecha_str = data.get('fecha')
                resultado = data.get('resultado', 'APROBADO')
                certificado = data.get('certificado', '')
                obs = data.get('observaciones', '')
                archivo = None
            
            instrumento = Instrumento.objects.get(id=inst_id)
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            
            HistorialCalibracion.objects.create(
                instrumento=instrumento, fecha_calibracion=fecha, resultado=resultado,
                certificado_nro=certificado, archivo_certificado=archivo, observaciones=obs, usuario=request.user
            )
            if resultado == 'APROBADO':
                instrumento.ultima_calibracion = fecha
                instrumento.certificado_nro = certificado
                instrumento.proxima_calibracion = fecha + relativedelta(months=instrumento.frecuencia_meses)
                instrumento.en_servicio = True
            else: instrumento.en_servicio = False
            instrumento.save()
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@supervisor_required
def dashboard_calibracion(request):
    activos = Instrumento.objects.filter(es_obsoleto=False)
    en_uso = activos.filter(en_servicio=True)
    vencidos_count = len([i for i in en_uso if i.is_calibracion_vencida()])
    alerta_count = len([i for i in en_uso if i.is_en_alerta()])
    ok_count = len([i for i in en_uso if not i.is_calibracion_vencida() and not i.is_en_alerta()])
    bloqueados_count = activos.filter(en_servicio=False).count()
    propios_count = activos.filter(es_propio=True).count()
    clientes_count = activos.filter(es_propio=False).count()
    obsoletos_count = Instrumento.objects.filter(es_obsoleto=True).count()
    
    tipos_count = {}
    for choice in Instrumento.TIPO_CHOICES:
        count = activos.filter(tipo=choice[0]).count()
        if count > 0: tipos_count[choice[1]] = count
    prox_calibraciones = activos.order_by('proxima_calibracion')[:15]
    return render(request, 'mediciones/dashboard_calibracion.html', {
        'vencidos_count': vencidos_count, 'alerta_count': alerta_count, 'ok_count': ok_count,
        'bloqueados_count': bloqueados_count, 'fuera_servicio_count': bloqueados_count,
        'propios_count': propios_count, 'clientes_count': clientes_count, 'obsoletos_count': obsoletos_count,
        'tipos_count': tipos_count, 'prox_calibraciones': prox_calibraciones,
    })

@supervisor_required
def lista_estructuras(request):
    planillas = PlanillaMedicion.objects.all().order_by('-id')
    unique_structures = []
    seen = set()
    for p in planillas:
        key = (p.num_op, p.proyecto)
        if key not in seen:
            unique_structures.append(p)
            seen.add(key)
    return render(request, 'mediciones/lista_estructuras.html', {'estructuras': unique_structures})

@supervisor_required
def eliminar_estructura(request):
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            proyecto = data.get('proyecto')
            num_op = data.get('num_op')
            filters = {}
            if proyecto: filters['proyecto'] = proyecto
            if num_op: filters['num_op'] = num_op
            if not filters: return JsonResponse({'status': 'error', 'message': 'Faltan parámetros.'})
            deleted_count, _ = PlanillaMedicion.objects.filter(**filters).delete()
            if deleted_count > 0:
                messages.success(request, 'Estructura eliminada correctamente.')
                return JsonResponse({'status': 'success', 'message': 'Estructura eliminada.'})
            else: return JsonResponse({'status': 'error', 'message': 'No se encontró la estructura.'})
        except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Método no permitido.'})

@supervisor_required
def configurar_estructura(request):
    edit_op = request.GET.get('op')
    edit_proy = request.GET.get('proy')
    existing_data = None
    if edit_op or edit_proy:
        filters = {}
        if edit_op: filters['num_op'] = edit_op
        if edit_proy: filters['proyecto'] = edit_proy
        related_planillas = PlanillaMedicion.objects.filter(**filters)
        if related_planillas.exists():
            first = related_planillas[0]
            existing_data = {'cliente_id': first.cliente_id, 'proyecto': first.proyecto, 'articulo_id': first.articulo_id, 'num_op': first.num_op, 'procesos': []}
            for p in related_planillas:
                if p.proceso_id is None: continue
                p_nombre = 'Sin Proceso'
                try:
                    if p.proceso: p_nombre = p.proceso.nombre
                    elif p.proceso_id: p_nombre = Proceso.objects.get(pk=p.proceso_id).nombre
                except Exception: p_nombre = f"Proceso {p.proceso_id}"
                e_nombre = ''
                try:
                    if p.elemento: e_nombre = p.elemento.nombre
                    elif p.elemento_id: e_nombre = Elemento.objects.get(pk=p.elemento_id).nombre
                except Exception: pass

                p_info = {'planilla_id': p.id, 'id': p.proceso_id, 'nombre': p_nombre, 'elemento_id': p.elemento_id if p.elemento_id else '', 'elemento_nombre': e_nombre, 'controles': []}
                tolerancias = Tolerancia.objects.filter(planilla=p).order_by('posicion')
                for t in tolerancias:
                    p_info['controles'].append({
                        'id': t.control_id, 'nombre': t.control.nombre,
                        'min': float(t.minimo) if t.minimo is not None else '',
                        'nom': float(t.nominal) if t.nominal is not None else '',
                        'max': float(t.maximo) if t.maximo is not None else ''
                    })
                existing_data['procesos'].append(p_info)

    if request.method == 'POST':
        import json
        try:
            data_json = request.POST.get('estructura_data')
            if not data_json: return JsonResponse({'status': 'error', 'message': 'No se recibieron datos'}, status=400)
            data = json.loads(data_json)
            cliente_id = data.get('cliente')
            proyecto = data.get('proyecto')
            articulo_id = data.get('articulo')
            num_op = data.get('num_op') or 0
            
            cliente = Cliente.objects.get(id=cliente_id) if cliente_id else None
            articulo = Articulo.objects.get(id=articulo_id) if articulo_id else None
            original_op = data.get('original_op')
            original_proyecto = data.get('original_proyecto')
            lookup_op = original_op if original_op is not None else num_op
            lookup_proy = original_proyecto if original_proyecto is not None else proyecto

            existing_planillas = list(PlanillaMedicion.objects.filter(proyecto=lookup_proy, num_op=lookup_op))
            processed_planillas_ids = []
            procesos_data = data.get('procesos', [])
            
            for p_data in procesos_data:
                proceso_id = p_data.get('id')
                proceso = Proceso.objects.get(id=proceso_id)
                elemento_id = p_data.get('elemento_id')
                elemento = None
                if elemento_id:
                     try: elemento = Elemento.objects.get(id=elemento_id)
                     except Elemento.DoesNotExist: pass
                else:
                    elemento_nombre = p_data.get('elemento_nombre')
                    if elemento_nombre: elemento, _ = Elemento.objects.get_or_create(nombre=elemento_nombre)

                match_planilla = None
                input_planilla_id = p_data.get('planilla_id')
                if input_planilla_id:
                    try: match_planilla = PlanillaMedicion.objects.get(id=input_planilla_id)
                    except PlanillaMedicion.DoesNotExist: pass
                
                if not match_planilla:
                    for ep in existing_planillas:
                        if ep.proceso_id == int(proceso_id) and ep.elemento == elemento:
                            match_planilla = ep
                            break
                if match_planilla:
                    match_planilla.cliente = cliente
                    match_planilla.articulo = articulo
                    match_planilla.proceso = proceso
                    match_planilla.elemento = elemento
                    match_planilla.proyecto = proyecto 
                    match_planilla.num_op = num_op
                    match_planilla.save()
                    planilla = match_planilla
                else:
                    planilla = PlanillaMedicion.objects.create(cliente=cliente, proyecto=proyecto, articulo=articulo, proceso=proceso, elemento=elemento, num_op=num_op)
                
                processed_planillas_ids.append(planilla.id)
                existing_tols = list(Tolerancia.objects.filter(planilla=planilla))
                processed_tol_ids = []
                controles_data = p_data.get('controles', [])
                
                for idx, c_data in enumerate(controles_data):
                    control_id = c_data.get('id')
                    try: control = Control.objects.get(id=control_id)
                    except Control.DoesNotExist: continue
                        
                    def to_decimal(val):
                        if val == '' or val is None: return None
                        try:
                            if isinstance(val, str): val = val.replace(',', '.')
                            return float(val)
                        except: return None

                    min_val = to_decimal(c_data.get('min'))
                    nom_val = to_decimal(c_data.get('nom'))
                    max_val = to_decimal(c_data.get('max'))

                    match_tol = None
                    for et in existing_tols:
                        if et.control_id == int(control_id):
                            match_tol = et
                            break
                    if match_tol:
                        match_tol.minimo = min_val
                        match_tol.nominal = nom_val
                        match_tol.maximo = max_val
                        match_tol.posicion = idx + 1
                        match_tol.save()
                        processed_tol_ids.append(match_tol.id)
                    else:
                        new_tol = Tolerancia.objects.create(planilla=planilla, control=control, minimo=min_val, nominal=nom_val, maximo=max_val, posicion=idx + 1)
                        processed_tol_ids.append(new_tol.id)
                
                for et in existing_tols:
                    if et.id not in processed_tol_ids: et.delete()

            for ep in existing_planillas:
                if ep.id not in processed_planillas_ids: ep.delete()
            
            return JsonResponse({'status': 'success', 'message': 'Estructura actualizada.', 'redirect_url': reverse('lista_estructuras')})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    clientes = Cliente.objects.all().order_by('nombre')
    articulos = Articulo.objects.all().order_by('nombre')
    procesos = Proceso.objects.all().order_by('nombre')
    controles = Control.objects.all().order_by('nombre')
    elementos = Elemento.objects.all().order_by('nombre')
    context = {'clientes': clientes, 'articulos': articulos, 'procesos_list': procesos, 'elementos_list': elementos, 'controles_list': controles, 'existing_data': existing_data, 'titulo': 'Editar Estructura' if existing_data else 'Configurar Estructura'}
    return render(request, 'mediciones/configurar_estructura.html', context)

@login_required
def nueva_medicion_op(request):
    proy_query = request.GET.get('proy', '').strip()
    op_query = request.GET.get('op', '').strip()
    proc_id = request.GET.get('proc', '').strip()
    pieza_actual = request.GET.get('pieza', 1)
    
    try: pieza_actual = int(str(pieza_actual).strip())
    except: pieza_actual = 1
    planilla = None
    rows = []
    piezas_medidas = []
    piezas_mostrar = []
    first_p = last_p = prev_p = next_p = None
    
    if op_query:
        if op_query.isdigit():
            planillas = PlanillaMedicion.objects.filter(num_op=op_query)
            if not planillas.exists(): planillas = PlanillaMedicion.objects.filter(num_op=int(op_query))
        else: planillas = PlanillaMedicion.objects.filter(num_op=op_query)

        if proy_query: planillas = planillas.filter(proyecto=proy_query)
        if proc_id and proc_id != 'None' and str(proc_id).isdigit(): planillas = planillas.filter(proceso_id=proc_id)
        planillas = planillas.select_related('elemento', 'proceso', 'cliente', 'articulo')

        if planillas.exists():
            planilla = planillas.first()
            tolerancias = Tolerancia.objects.filter(planilla__in=planillas).select_related('control', 'planilla__elemento', 'planilla__proceso').order_by('planilla__elemento__nombre', 'posicion')
            
            if request.method == 'POST':
                maquina_id = request.POST.get('maquina_id')
                if maquina_id: planillas.update(maquina=maquina_id)

                for tol in tolerancias:
                    instr_id = request.POST.get(f'instrumento_{tol.id}')
                    if instr_id:
                        tol.instrumento_id = instr_id
                        tol.save()

                    if tol.control.pnp:
                        val_input = request.POST.get(f'valorpnp_{tol.id}')
                        if val_input is not None:
                            val_obj, _ = ValorMedicion.objects.update_or_create(
                                planilla=tol.planilla, control=tol.control, pieza=pieza_actual, tolerancia=tol,
                                defaults={'posicion': tol.posicion, 'op': str(tol.planilla.num_op) if tol.planilla.num_op else ''}
                            )
                            val_obj.valor_pnp = val_input if val_input else None
                            val_obj.valor_pieza = None
                            val_obj.save()
                    else:
                        val_input = request.POST.get(f'valor_{tol.id}')
                        if val_input is not None:
                            val_obj, _ = ValorMedicion.objects.update_or_create(
                                planilla=tol.planilla, control=tol.control, pieza=pieza_actual, tolerancia=tol,
                                defaults={'posicion': tol.posicion, 'op': str(tol.planilla.num_op) if tol.planilla.num_op else ''}
                            )
                            val_obj.valor_pnp = None
                            if val_input.strip() == '': val_obj.valor_pieza = None
                            else:
                                try:
                                    clean_val = val_input.replace(',', '.')
                                    val_obj.valor_pieza = float(clean_val)
                                except: pass
                            val_obj.save()
                
                messages.success(request, f'Mediciones de Pieza {pieza_actual} guardadas.')
                if 'guardar_siguiente' in request.POST:
                    return redirect(f"{reverse('nueva_medicion_op')}?proy={proy_query}&op={op_query}&proc={proc_id}&pieza={pieza_actual + 1}")

            valores_existentes = ValorMedicion.objects.filter(planilla__in=planillas, pieza=pieza_actual)
            valores_dict = { (v.planilla_id, v.control_id): v for v in valores_existentes }
            
            from .utils_spc import SPCAnalyzer
            visible_control_ids = [t.control_id for t in tolerancias]
            history_dict = {}
            all_history = ValorMedicion.objects.filter(planilla__in=planillas, control_id__in=visible_control_ids, pieza__lte=pieza_actual).order_by('pieza')
            
            for v in all_history:
                key = f"tol_{v.tolerancia_id}" if v.tolerancia_id else f"pc_{v.planilla_id}_{v.control_id}"
                if key not in history_dict: history_dict[key] = []
                if v.valor_pieza is not None: history_dict[key].append(float(v.valor_pieza))

            for tol in tolerancias:
                val_obj = valores_dict.get((tol.planilla_id, tol.control_id))
                current_val = None
                status = 'PENDIENTE'
                spc_alerts = []
                
                if not tol.control.pnp:
                    min_limit, max_limit = tol.get_absolute_limits()
                    h_values = history_dict.get(f"tol_{tol.id}", [])
                    if not h_values: h_values = history_dict.get(f"pc_{tol.planilla_id}_{tol.control_id}", [])

                    analyzer = SPCAnalyzer(h_values, nominal=tol.nominal, min_limit=min_limit, max_limit=max_limit)
                    nelson_violations = analyzer.check_nelson_rules()
                    last_idx = len(h_values) - 1
                    for v in nelson_violations:
                        if v['point'] == last_idx:
                            spc_alerts.append({'message': f"📍 {tol.control.nombre}: {v['desc']}", 'severity': v['severity']})
                
                if val_obj:
                    if tol.control.pnp:
                        current_val = val_obj.valor_pnp
                        status = 'OK' if current_val == 'OK' else ('NOK' if current_val == 'NOK' else 'PENDIENTE')
                    else:
                        current_val = val_obj.valor_pieza
                        if current_val is not None:
                            try:
                                val_f = float(current_val)
                                min_limit, max_limit = tol.get_absolute_limits()
                                is_ok = (min_limit is None or val_f >= min_limit) and (max_limit is None or val_f <= max_limit)
                                status = 'OK' if is_ok else 'NOK'
                            except: status = 'ERROR'
                
                abs_min, abs_max = tol.get_absolute_limits()
                rows.append({
                    'tolerancia': tol, 'valor': current_val, 'status': status, 'min_limit': abs_min, 'max_limit': abs_max,
                    'spc_alerts': spc_alerts, 'has_warning': any(a['severity'] == 'warning' for a in spc_alerts),
                    'has_danger': any(a['severity'] == 'danger' for a in spc_alerts)
                })
            planilla = planillas.first()

        piezas_medidas = ValorMedicion.objects.filter(planilla__in=planillas).values_list('pieza', flat=True).distinct().order_by('pieza')
        max_p = piezas_medidas.last() if piezas_medidas.exists() else 0
        range_piezas = list(piezas_medidas)
        
        try: p_actual_int_nav = int(str(pieza_actual))
        except: p_actual_int_nav = 0
        if p_actual_int_nav >= max_p:
            if (max_p + 1) not in range_piezas: range_piezas.append(max_p + 1)
        
        try:
            p_actual_int = int(pieza_actual)
            current_idx = range_piezas.index(p_actual_int) if p_actual_int in range_piezas else -1
        except: current_idx = -1
            
        first_p = range_piezas[0] if range_piezas else 1
        last_p = range_piezas[-1] if range_piezas else 1
        prev_p = range_piezas[current_idx - 1] if current_idx > 0 else None
        next_p = range_piezas[current_idx + 1] if current_idx != -1 and current_idx < len(range_piezas) - 1 else None
        
        window_size = 4
        if len(range_piezas) <= window_size: piezas_mostrar = range_piezas
        else:
            if current_idx == -1: piezas_mostrar = range_piezas[:window_size]
            else:
                start = max(0, current_idx - 1)
                end = start + window_size
                if end > len(range_piezas):
                    end = len(range_piezas)
                    start = max(0, end - window_size)
                piezas_mostrar = range_piezas[start:end]

    proyectos = PlanillaMedicion.objects.values_list('proyecto', flat=True).distinct().order_by('proyecto')
    ops_disponibles = []
    if proy_query: ops_disponibles = PlanillaMedicion.objects.filter(proyecto=proy_query).values_list('num_op', flat=True).distinct().order_by('num_op')
    procesos_disponibles = []
    if proy_query and op_query:
        p_ids = PlanillaMedicion.objects.filter(proyecto=proy_query, num_op=op_query).values_list('proceso_id', flat=True).distinct()
        procesos_disponibles = Proceso.objects.filter(id__in=p_ids).order_by('nombre')

    context = {
        'proyectos': proyectos, 'ops_disponibles': ops_disponibles, 'procesos_disponibles': procesos_disponibles,
        'query_proy': proy_query, 'query_op': int(op_query) if op_query and op_query.isdigit() else op_query,
        'query_proc': int(proc_id) if proc_id and proc_id != 'None' and proc_id.isdigit() else None,
        'planilla': planilla, 'rows': rows, 'pieza_actual': pieza_actual, 'piezas_medidas': list(piezas_medidas) if planilla else [],
        'piezas_navegacion': piezas_mostrar if planilla else [], 'first_p': first_p if planilla else None, 'last_p': last_p if planilla else None,
        'prev_p': prev_p if planilla else None, 'next_p': next_p if planilla else None, 'maquinas': Maquina.objects.all(), 'instrumentos': Instrumento.objects.all(), 'titulo': 'Ingreso de Mediciones'
    }
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        serializable_rows = []
        for r in rows:
            serializable_rows.append({
                'tolerancia_id': r['tolerancia'].id, 'control_nombre': r['tolerancia'].control.nombre,
                'instrumento_id': r['tolerancia'].instrumento.id if r['tolerancia'].instrumento else '',
                'instrumento_nombre': r['tolerancia'].instrumento.nombre if r['tolerancia'].instrumento else 'SIN INSTRUMENTO',
                'nominal': float(r['tolerancia'].nominal) if r['tolerancia'].nominal is not None else 0.000,
                'minimo': float(r['tolerancia'].minimo) if r['tolerancia'].minimo is not None else 0.000,
                'maximo': float(r['tolerancia'].maximo) if r['tolerancia'].maximo is not None else 0.000,
                'valor': r['valor'] if (r['tolerancia'].control.pnp or r['valor'] is None) else float(r['valor']),
                'status': r['status'], 'min_limit': float(r['min_limit']) if r['min_limit'] is not None else None,
                'max_limit': float(r['max_limit']) if r['max_limit'] is not None else None, 'spc_alerts': r['spc_alerts'],
                'has_warning': r['has_warning'], 'has_danger': r['has_danger'], 'is_pnp': r['tolerancia'].control.pnp
            })
        return JsonResponse({'status': 'success', 'pieza_actual': pieza_actual, 'piezas_medidas': list(piezas_medidas) if planilla else [], 'piezas_navegacion': piezas_mostrar if planilla else [], 'first_p': first_p, 'last_p': last_p, 'prev_p': prev_p, 'next_p': next_p, 'rows': serializable_rows, 'observaciones': planilla.observaciones if planilla else ''})
    return render(request, 'mediciones/nueva_medicion_op.html', context)

@csrf_exempt
@login_required
def guardar_medicion_ajax(request):
    if request.method == 'POST':
        import json, logging
        logger = logging.getLogger(__name__)
        data = json.loads(request.body)
        tol_id = data.get('tolerancia_id')
        pieza = data.get('pieza')
        valor = data.get('valor')
        
        try:
            tol = Tolerancia.objects.get(id=tol_id)
            pieza_int = int(str(pieza))
            val_obj, _ = ValorMedicion.objects.update_or_create(
                planilla=tol.planilla, control=tol.control, pieza=pieza_int,
                defaults={'tolerancia': tol, 'posicion': tol.posicion, 'op': str(tol.planilla.num_op) if tol.planilla.num_op else ''}
            )
            if tol.control.pnp:
                val_obj.valor_pnp = valor
                val_obj.valor_pieza = None
            else:
                if valor and valor.strip():
                    try:
                        clean_valor = valor.replace(',', '.')
                        val_num = float(clean_valor)
                        val_obj.valor_pieza = val_num
                        min_l, max_l = tol.get_absolute_limits()
                        if min_l is not None and max_l is not None:
                            val_obj.valor_pnp = 'OK' if min_l <= val_num <= max_l else 'NOK'
                        else: val_obj.valor_pnp = 'OK'
                    except:
                        val_obj.valor_pieza = None
                        val_obj.valor_pnp = 'NOK'
                else:
                    val_obj.valor_pieza = None
                    val_obj.valor_pnp = None
            val_obj.save()
            return JsonResponse({'status': 'success', 'saved_value': val_obj.valor_pieza if not tol.control.pnp else val_obj.valor_pnp})
        except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)

@csrf_exempt
def guardar_maquina_ajax(request):
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        maquina_id = data.get('maquina_id')
        proy = data.get('proyecto', '').strip()
        op = data.get('op', '').strip()
        proc_id = data.get('proceso_id', '').strip()
        
        if maquina_id == "" or maquina_id == "null": maquina_id = None
        if op.isdigit():
            q = PlanillaMedicion.objects.filter(proyecto=proy, num_op=op)
            if not q.exists(): q = PlanillaMedicion.objects.filter(proyecto=proy, num_op=int(op))
        else: q = PlanillaMedicion.objects.filter(proyecto=proy, num_op=op)
        if proc_id and proc_id != 'None' and str(proc_id).isdigit(): q = q.filter(proceso_id=proc_id)
        count = q.update(maquina_id=maquina_id)
        return JsonResponse({'status': 'success', 'updated_count': count})
    return JsonResponse({'status': 'error'}, status=405)

@csrf_exempt
def guardar_instrumento_ajax(request):
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        tol_id = data.get('tolerancia_id')
        instr_id = data.get('instrumento_id')
        if instr_id == "": instr_id = None
        try:
            Tolerancia.objects.filter(id=tol_id).update(instrumento_id=instr_id)
            return JsonResponse({'status': 'success'})
        except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error'}, status=405)

@csrf_exempt
@supervisor_required
def eliminar_pieza_ajax(request):
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            proy = data.get('proyecto')
            op = data.get('op')
            proc_id = data.get('proceso_id')
            pieza = data.get('pieza')
            if not proy or not op or not pieza: return JsonResponse({'status': 'error', 'message': 'Faltan parámetros'}, status=400)
            planillas = PlanillaMedicion.objects.filter(proyecto=proy, num_op=op)
            if not planillas.exists() and str(op).isdigit(): planillas = PlanillaMedicion.objects.filter(proyecto=proy, num_op=int(op))
            if proc_id and str(proc_id).isdigit(): planillas = planillas.filter(proceso_id=proc_id)
            
            if planillas.exists():
                try:
                    pieza_int = int(str(pieza))
                    count, _ = ValorMedicion.objects.filter(planilla__in=planillas, pieza=pieza_int).delete()
                    return JsonResponse({'status': 'success', 'deleted': count})
                except ValueError: return JsonResponse({'status': 'error', 'message': 'Pieza inválida'}, status=400)
            else: return JsonResponse({'status': 'error', 'message': 'No encontradas'}, status=404)
        except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)

@csrf_exempt
@supervisor_required
def eliminar_planilla_completa_ajax(request, planilla_id):
    if request.method == 'POST':
        try:
            planilla = get_object_or_404(PlanillaMedicion, id=planilla_id)
            ValorMedicion.objects.filter(planilla=planilla).delete()
            planilla.tolerancia_set.all().delete()
            planilla.delete()
            return JsonResponse({'status': 'success'})
        except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Solo POST permitido'}, status=405)

@supervisor_required
def estadisticas_control(request, tolerancia_id):
    import math, statistics
    tolerancia = get_object_or_404(Tolerancia, id=tolerancia_id)
    valores_query = ValorMedicion.objects.filter(planilla=tolerancia.planilla, control=tolerancia.control).order_by('pieza')
    
    data_points = []
    labels = []
    for v in valores_query:
        if v.valor_pieza is not None:
            data_points.append(float(v.valor_pieza))
            labels.append(str(v.pieza))

    from .utils_spc import SPCAnalyzer
    lsl, usl = tolerancia.get_absolute_limits()
    analyzer = SPCAnalyzer(data_points, nominal=tolerancia.nominal, min_limit=lsl, max_limit=usl, subgroup_size=5)
    xr_data = analyzer.get_xr_data()
    nelson_violations = analyzer.check_nelson_rules()
    cp, cpk = analyzer.get_capability_indices()

    def safe_round(val, digits=4):
        if val is None: return None
        try:
            if math.isinf(val) or math.isnan(val): return None
            return round(float(val), digits)
        except: return None

    def get_capability_status(value):
        if value is None: return None
        if value < 1.0: return {'text': 'INACEPTABLE', 'class': 'badge-soft-danger'}
        elif value < 1.33: return {'text': 'BAJA CAPACIDAD', 'class': 'badge-soft-warning'}
        elif value < 1.67: return {'text': 'CAPAZ', 'class': 'badge-soft-success'}
        else: return {'text': 'EXCELENTE', 'class': 'badge-soft-excellent'}

    n_approved = 0
    n_rejected = 0
    for v in valores_query:
        if tolerancia.control.pnp:
            if v.valor_pnp == 'OK': n_approved += 1
            elif v.valor_pnp == 'NOK': n_rejected += 1
        else:
            if v.valor_pieza is not None:
                try:
                    vf = float(v.valor_pieza)
                    is_ok = (lsl is None or vf >= lsl) and (usl is None or vf <= usl)
                    if not is_ok: n_rejected += 1
                    else: n_approved += 1
                except: pass

    stats = {
        'n': max(len(data_points), n_approved + n_rejected), 'mean': safe_round(analyzer.mean), 'stdev': safe_round(analyzer.std),
        'min': safe_round(min(data_points)) if data_points else None, 'max': safe_round(max(data_points)) if data_points else None,
        'range': safe_round(max(data_points) - min(data_points)) if data_points else None, 'lsl': safe_round(lsl), 'usl': safe_round(usl),
        'cp': safe_round(cp, 2), 'cpk': safe_round(cpk, 2), 'cp_info': get_capability_status(cp), 'cpk_info': get_capability_status(cpk),
        'nominal': safe_round(tolerancia.nominal), 'lic': safe_round(analyzer.mean - 3 * analyzer.std) if analyzer.mean and analyzer.std else None,
        'lsc': safe_round(analyzer.mean + 3 * analyzer.std) if analyzer.mean and analyzer.std else None,
        'n_approved': n_approved, 'n_rejected': n_rejected, 'n_total': n_approved + n_rejected
    }

    if xr_data:
        stats.update({
            'avg_range': safe_round(xr_data['avg_range']), 'ucl_x': safe_round(xr_data['ucl_x']), 'lcl_x': safe_round(xr_data['lcl_x']),
            'ucl_r': safe_round(xr_data['ucl_r']), 'lcl_r': safe_round(xr_data['lcl_r']), 'num_subgroups': xr_data['num_subgroups'],
            'x_bars': [safe_round(x) for x in xr_data['x_bars']], 'ranges': [safe_round(r) for r in xr_data['ranges']],
        })

    alerts = []
    icon_map = {1: 'ri-error-warning-line', 2: 'ri-line-chart-line', 3: 'ri-funds-line', 4: 'ri-pulse-line'}
    type_map = {1: 'danger', 2: 'warning', 3: 'warning', 4: 'info'}
    for v in nelson_violations:
        alerts.append({'title': v['title'], 'desc': v['desc'], 'type': type_map.get(v['rule'], 'secondary'), 'icon': icon_map.get(v['rule'], 'ri-information-line')})
    if cpk is not None and cpk < 1.0:
        alerts.append({'title': 'Capacidad Crítica', 'desc': 'Índice CPK fuera de norma.', 'type': 'danger', 'icon': 'ri-close-circle-line'})
    stats['alerts'] = alerts

    hermanos = Tolerancia.objects.filter(planilla__proyecto=tolerancia.planilla.proyecto, planilla__num_op=tolerancia.planilla.num_op).select_related('control', 'planilla', 'planilla__elemento').order_by('planilla__elemento__nombre', 'posicion')
    context = {'tolerancia': tolerancia, 'controles_hermanos': hermanos, 'stats': stats, 'data_points': data_points, 'labels': labels, 'stats_json': json.dumps(stats), 'data_points_json': json.dumps(data_points), 'labels_json': json.dumps(labels), 'titulo': f'SPC - {tolerancia.control.nombre}', 'is_xr_available': xr_data is not None, 'is_pnp': tolerancia.control.pnp}

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'stats': stats, 'data_points': data_points, 'labels': labels, 'control_nombre': tolerancia.control.nombre, 'id': tolerancia.id, 'planilla_id': tolerancia.planilla.id, 'is_xr_available': xr_data is not None, 'proceso_id': tolerancia.planilla.proceso.id if tolerancia.planilla.proceso else '', 'proceso_nombre': tolerancia.planilla.proceso.nombre if tolerancia.planilla.proceso else 'S/P', 'num_op': tolerancia.planilla.num_op, 'proyecto': tolerancia.planilla.proyecto, 'cliente': tolerancia.planilla.cliente.nombre if tolerancia.planilla.cliente else 'S/C'})
    return render(request, 'mediciones/estadisticas_control.html', context)

@login_required
def panel_control_geografico(request):
    maquinas = Maquina.objects.all()
    maquina_status = []
    for m in maquinas:
        last_planilla = PlanillaMedicion.objects.filter(maquina=m).order_by('-id').first()
        status = 'neutral'
        info = "Sin datos recientes"
        if last_planilla:
            valores = ValorMedicion.objects.filter(planilla=last_planilla).select_related('tolerancia', 'control')
            if valores.exists():
                is_nok = False
                for v in valores:
                    if v.control.pnp:
                        if v.valor_pnp == 'NOK': is_nok = True; break
                    else:
                        if v.valor_pieza is not None and v.tolerancia:
                            min_l, max_l = v.tolerancia.get_absolute_limits()
                            if min_l is not None and max_l is not None:
                                if v.valor_pieza < min_l or v.valor_pieza > max_l: is_nok = True; break
                status = 'failed' if is_nok else 'approved'
                info = f"OP: {last_planilla.num_op} - {last_planilla.proceso.nombre if last_planilla.proceso else ''}"
            
        maquina_status.append({'id': m.id, 'nombre': m.nombre, 'codigo': m.codigo, 'x_pos': m.x_pos or 0, 'y_pos': m.y_pos or 0, 'status': status, 'info': info})
    return render(request, 'mediciones/panel_geografico.html', {'maquina_status': maquina_status})

@csrf_exempt
@supervisor_required
def api_update_maquina_pos(request):
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            m = Maquina.objects.get(id=data.get('id'))
            m.x_pos, m.y_pos = data.get('x'), data.get('y')
            m.save()
            return JsonResponse({'status': 'success'})
        except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

@login_required
def modo_operario(request): return render(request, 'mediciones/operario_medicion.html')

@login_required
def operario_medicion(request): return render(request, 'mediciones/operario_medicion.html')

@login_required
def api_buscar_op_endpoint(request, op):
    try: planillas = PlanillaMedicion.objects.filter(num_op=int(str(op).strip())).select_related('proceso', 'cliente')
    except: planillas = PlanillaMedicion.objects.filter(num_op=op).select_related('proceso', 'cliente')
    if not planillas.exists(): planillas = PlanillaMedicion.objects.filter(num_op__icontains=str(op)).select_related('proceso', 'cliente')
    if not planillas.exists(): return JsonResponse({'status': 'error', 'message': f'No se encontró la OP #{op}.'})
    
    unique_procs = {}
    for p in planillas:
        proc_id = p.proceso.id if p.proceso else 0
        key = f"{p.proyecto}_{proc_id}"
        if key not in unique_procs:
            unique_procs[key] = {'id': p.id, 'proyecto': p.proyecto or 'Sin Proyecto', 'proceso_id': proc_id, 'proceso_nombre': p.proceso.nombre if p.proceso else 'Sin Proceso', 'op': p.num_op, 'cliente': p.cliente.nombre if p.cliente else 'Sin Cliente'}
    results = list(unique_procs.values())
    return JsonResponse({'status': 'success', 'count': len(results), 'results': results, 'proyecto': results[0]['proyecto'] if len(results) > 0 else '', 'proceso_id': results[0]['proceso_id'] if len(results) > 0 else ''})

@login_required
def api_operario_data(request):
    proy, op, proc_id, pieza = request.GET.get('proy', '').strip(), request.GET.get('op', '').strip(), request.GET.get('proc', '').strip(), request.GET.get('pieza', '1').strip()
    try: pieza = int(pieza)
    except: pieza = 1
    if not proy or not op: return JsonResponse({'status': 'error', 'message': 'Faltan parámetros.'})
    try:
        op_clean = str(op).strip()
        planillas = PlanillaMedicion.objects.filter(proyecto=proy, num_op=int(op_clean)) if op_clean.isdigit() else PlanillaMedicion.objects.filter(proyecto=proy, num_op=op_clean)
    except: planillas = PlanillaMedicion.objects.filter(proyecto=proy, num_op=op)
    if proc_id and proc_id != 'None' and proc_id.isdigit(): planillas = planillas.filter(proceso_id=proc_id)
    planillas = planillas.select_related('cliente', 'proceso', 'elemento')
    if not planillas.exists(): return JsonResponse({'status': 'error', 'message': 'No se encontraron planillas.'})
    
    first_planilla = planillas.first()
    tolerancias = Tolerancia.objects.filter(planilla__in=planillas).select_related('control', 'planilla__elemento', 'planilla__proceso', 'instrumento').order_by('planilla__elemento__nombre', 'posicion')
    valores_existentes = ValorMedicion.objects.filter(planilla__in=planillas, pieza=pieza)
    valores_dict = {(v.planilla_id, v.control_id): v for v in valores_existentes}
    
    rows = []
    for tol in tolerancias:
        val_obj = valores_dict.get((tol.planilla_id, tol.control_id))
        current_val, status = None, 'pending'
        if val_obj:
            if tol.control.pnp:
                current_val = val_obj.valor_pnp
                status = 'ok' if current_val == 'OK' else ('nok' if current_val == 'NOK' else 'pending')
            else:
                current_val = val_obj.valor_pieza
                if current_val is not None:
                    try:
                        val_f = float(current_val)
                        min_l, max_l = tol.get_absolute_limits()
                        is_ok = (min_l is None or val_f >= min_l) and (max_l is None or val_f <= max_l)
                        status = 'ok' if is_ok else 'nok'
                    except: status = 'pending'
        rows.append({'tolerancia_id': tol.id, 'control_nombre': tol.control.nombre, 'is_pnp': tol.control.pnp, 'nominal': float(tol.nominal) if tol.nominal is not None else None, 'tol_min': float(tol.minimo) if tol.minimo is not None else None, 'tol_max': float(tol.maximo) if tol.maximo is not None else None, 'valor': current_val, 'status': status, 'instrumento_id': tol.instrumento_id, 'elemento_nombre': tol.planilla.elemento.nombre if tol.planilla.elemento else None})
    
    piezas_medidas = list(ValorMedicion.objects.filter(planilla__in=planillas).values_list('pieza', flat=True).distinct().order_by('pieza'))
    max_p = max(piezas_medidas) if piezas_medidas else 0
    range_piezas = list(piezas_medidas)
    if (max_p + 1) not in range_piezas: range_piezas.append(max_p + 1)
    if pieza not in range_piezas: range_piezas.append(pieza); range_piezas.sort()
    
    window_size = 6
    try: current_idx = range_piezas.index(pieza)
    except ValueError: current_idx = 0
    if len(range_piezas) <= window_size: piezas_mostrar = range_piezas
    else:
        start = max(0, current_idx - 2)
        end = start + window_size
        if end > len(range_piezas): end = len(range_piezas); start = max(0, end - window_size)
        piezas_mostrar = range_piezas[start:end]
    
    return JsonResponse({'status': 'success', 'proyecto': first_planilla.proyecto or '', 'op': first_planilla.num_op, 'cliente': first_planilla.cliente.nombre if first_planilla.cliente else '-', 'proceso': first_planilla.proceso.nombre if first_planilla.proceso else '-', 'pieza_actual': pieza, 'piezas': piezas_mostrar, 'piezas_con_datos': piezas_medidas, 'rows': rows, 'instrumentos': list(Instrumento.objects.all().values('id', 'nombre').order_by('nombre'))})

@login_required
def exportar_pdf(request, planilla_id):
    planilla = get_object_or_404(PlanillaMedicion, id=planilla_id)
    planilla.aprobador, planilla.fecha_aprobador = request.user, datetime.date.today()
    planilla.save()
    
    tolerancias = Tolerancia.objects.filter(planilla=planilla).select_related('control', 'instrumento').order_by('posicion')
    valores = ValorMedicion.objects.filter(planilla=planilla).select_related('tolerancia', 'control')
    valores_dict, piezas_set = {}, set()
    for v in valores:
        valores_dict[(v.tolerancia_id, v.pieza)] = v.valor_pnp if v.control.pnp else v.valor_pieza
        piezas_set.add(v.pieza)
    piezas_ordenadas = sorted(list(piezas_set))
    
    rows = []
    for tol in tolerancias:
        p_data = [{'num': p, 'val': valores_dict.get((tol.id, p)) if valores_dict.get((tol.id, p)) is not None else ''} for p in piezas_ordenadas]
        tol_str = "PASA / NO PASA" if tol.control.pnp else f"{tol.minimo:g} / {tol.maximo:g}"
        rows.append({'detalle': tol.control.nombre, 'solicitado': f"{tol.nominal:g}" if tol.nominal is not None else "-", 'tolerancia': tol_str, 'instrumento': tol.instrumento.codigo if tol.instrumento and tol.instrumento.codigo else (tol.instrumento.nombre if tol.instrumento else "-"), 'piezas': p_data})

    first_valor = ValorMedicion.objects.filter(planilla=planilla).order_by('fecha').first()
    elaborador_nombre = "-"
    if first_valor and first_valor.id_operario:
        try: elaborador_nombre = User.objects.get(id=first_valor.id_operario).get_full_name()
        except: elaborador_nombre = f"Operario {first_valor.id_operario}"

    context = {'planilla': planilla, 'rows': rows, 'piezas_headers': piezas_ordenadas[:15], 'fecha_emision': timezone.now().strftime('%d/%m/%Y'), 'num_registro': 'RQ-11', 'rev': '00', 'rev_fecha': '24/06/2022', 'elaborador_nombre': elaborador_nombre, 'aprobador_nombre': request.user.get_full_name(), 'observaciones': planilla.observaciones or ""}
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Reporte_Calidad_OP_{planilla.num_op}.pdf"'
    pisa.CreatePDF(get_template('mediciones/reporte_calidad_pdf.html').render(context), dest=response)
    return response

@csrf_exempt
@login_required
def exportar_pdf_pro(request, planilla_id):
    from .utils_pdf import generate_xbar_chart, generate_r_chart, generate_capability_chart
    from .utils_spc import SPCAnalyzer
    import math
    planilla = get_object_or_404(PlanillaMedicion, id=planilla_id)
    tolerancias = Tolerancia.objects.filter(planilla=planilla).select_related('control', 'instrumento').order_by('posicion')
    params_spc = []
    
    for tol in tolerancias:
        if tol.control.pnp: continue
        valores_query = ValorMedicion.objects.filter(planilla=planilla, control=tol.control).order_by('pieza')
        data_points = [float(v.valor_pieza) for v in valores_query if v.valor_pieza is not None]
        labels = [f"P{v.pieza}" for v in valores_query if v.valor_pieza is not None]
        if not data_points: continue
        
        lsl, usl = tol.get_absolute_limits()
        analyzer = SPCAnalyzer(data_points, nominal=tol.nominal, min_limit=lsl, max_limit=usl, subgroup_size=5)
        xr_data = analyzer.get_xr_data()
        nelson_violations = analyzer.check_nelson_rules()
        cp, cpk = analyzer.get_capability_indices()
        
        def safe_r(val): return round(val, 4) if val is not None and not math.isinf(val) and not math.isnan(val) else None
        stats = {'n': len(data_points), 'mean': safe_r(analyzer.mean), 'stdev': safe_r(analyzer.std), 'range': safe_r(max(data_points) - min(data_points)), 'cp': safe_r(cp), 'cpk': safe_r(cpk), 'lic': safe_r(analyzer.mean - 3 * analyzer.std) if analyzer.mean and analyzer.std else None, 'lsc': safe_r(analyzer.mean + 3 * analyzer.std) if analyzer.mean and analyzer.std else None}
        
        alerts = [{'title': v['title'], 'desc': v['desc'], 'type': 'danger' if v['rule']==1 else 'warning'} for v in nelson_violations]
        if cpk is not None and cpk < 1.0: alerts.append({'title': 'Capacidad Crítica', 'desc': 'CPK fuera de norma.', 'type': 'danger'})
        stats['alerts'] = alerts

        params_spc.append({'nombre': tol.control.nombre, 'nominal': tol.nominal, 'lsl': lsl, 'usl': usl, 'stats': stats, 'charts': {'xbar': generate_xbar_chart(data_points, xr_data, labels), 'range': generate_r_chart(data_points, xr_data, labels), 'gauss': generate_capability_chart(data_points, tol.nominal, lsl, usl)}})

    context = {'planilla': planilla, 'params_spc': params_spc, 'fecha_emision': timezone.now().strftime('%d/%m/%Y')}
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Reporte_PRO_OP_{planilla.num_op}.pdf"'
    pisa.CreatePDF(get_template('mediciones/reporte_calidad_pro_pdf.html').render(context), dest=response)
    return response

@login_required
def guardar_observaciones_ajax(request):
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            p = PlanillaMedicion.objects.get(id=data.get('planilla_id'))
            p.observaciones = data.get('observaciones', '')
            p.save()
            return JsonResponse({'status': 'success'})
        except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def ocr_lector_planos(request):
    """
    Vista Lector OCR de Planos (PDF) - Canal Directo de IA con Imagen (PyMuPDF).
    """
    def render_error(msg):
        return render(request, 'mediciones/ocr_lector.html', {
            'error_ia': msg,
            'success': False
        })

    context = {}
    from .models import Profile
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        profile = Profile.objects.create(user=request.user)
    
    if request.method == 'POST':
        api_key_input = request.POST.get('api_key', '').strip()
        if api_key_input:
            profile.gemini_api_key = api_key_input
            profile.save()
            
    gemini_key = profile.gemini_api_key

    if request.method == 'POST' and request.FILES.get('plano_pdf'):
        pdf_file = request.FILES['plano_pdf']
        file_name = pdf_file.name
        
        fs = FileSystemStorage(location=os.path.join('media', 'temporales'))
        filename = fs.save(pdf_file.name, pdf_file)
        uploaded_file_path = fs.path(filename)
        
        print(f"[OCR-VIEW] Iniciando extracción local determinista para {file_name}...")
        try:
            # Leer con reintentos para evitar WinError 32 (archivo bloqueado por Windows)
            pdf_bytes = abrir_archivo_seguro(uploaded_file_path)

            # Llamada directa a extraer_datos_de_pdf local, omitiendo claves de API
            datos_ia = extraer_datos_de_pdf(
                pdf_bytes=pdf_bytes
            )
            
            if datos_ia is None or not isinstance(datos_ia, dict) or not datos_ia.get('matrix'):
                raise ValueError("El extractor local retornó un objeto vacío o no encontró la matriz de controles.")
            
            header_info = datos_ia.get('header') or {}
            extracted_matrix = datos_ia.get('matrix') or []
            piezas_cols = datos_ia.get('piezas') or []
            
            eliminar_archivo_seguro(uploaded_file_path)
        except Exception as ocr_error:
            eliminar_archivo_seguro(uploaded_file_path)
            print(f"[OCR-VIEW WARNING] OCR local falló, generando matriz en blanco. Detalle: {str(ocr_error)}")
            # Fallback limpio sin crashear
            header_info = {"denominacion": "LECTURA MANUAL REQUERIDA"}
            extracted_matrix = []
            piezas_cols = [str(i) for i in range(1, 11)]

        
        from .models import Proceso, Articulo, Elemento, Cliente
        auto_matched = {'proceso_id': '', 'articulo_id': '', 'elemento_id': '', 'cliente_id': ''}
        
        def find_best_match(model, query_text, field_name='nombre'):
             if not query_text: return None
             clean_query = str(query_text).strip().upper()
             res = model.objects.filter(**{f"{field_name}__iexact": clean_query}).first()
             if res: return res
             if clean_query.isdigit():
                  res = model.objects.filter(**{f"{field_name}__icontains": clean_query}).first()
                  if res: return res
             parts = clean_query.split()
             if len(parts) > 1:
                  res = model.objects.filter(**{f"{field_name}__icontains": " ".join(parts[:2])}).first()
                  if res: return res
             return model.objects.filter(**{f"{field_name}__icontains": clean_query[:30]}).first()

        c = find_best_match(Cliente, header_info.get('cliente'))
        if c: auto_matched['cliente_id'] = c.id
        a = find_best_match(Articulo, header_info.get('articulo'))
        if a: auto_matched['articulo_id'] = a.id
        p = find_best_match(Proceso, header_info.get('denominacion') or header_info.get('proceso'))
        if p: auto_matched['proceso_id'] = p.id
        e = find_best_match(Elemento, header_info.get('operacion') or header_info.get('elemento'))
        if e: auto_matched['elemento_id'] = e.id

        valid_matrix = []
        for row in extracted_matrix:
            try:
                nom_str = str(row['nominal']).replace(',', '.')
                nom_str_clean = re.sub(r'\(?\d+[xX]\)?', '', nom_str).strip()
                nom_nums = re.findall(r"[-+]?\d*\.\d+|\d+", nom_str_clean) or re.findall(r"[-+]?\d*\.\d+|\d+", nom_str)
                nom_float = float(nom_nums[0]) if nom_nums else 0.0
                
                tol_str = str(row['tolerancia']).replace(',', '.').strip()
                t_plus = t_minus = 0.0
                if '±' in tol_str:
                    try:
                        t_val = float(re.findall(r"\d*\.\d+|\d+", tol_str)[0])
                        t_plus = t_minus = t_val
                    except: pass
                elif '/' in tol_str or ('+' in tol_str and '-' in tol_str):
                    for m in re.findall(r"([+-]\s*\d*\.\d+|[+-]\s*\d+)", tol_str):
                        val = float(m.replace(' ', ''))
                        if '+' in m: t_plus = abs(val)
                        if '-' in m: t_minus = abs(val)
                else:
                    try:
                        t_val = float(re.findall(r"\d*\.\d+|\d+", tol_str)[0])
                        t_plus = t_minus = t_val
                    except: pass

                min_v, max_v = nom_float - t_minus, nom_float + t_plus
                processed_vals = []
                row_valores = row.get('valores', [])
                if isinstance(row_valores, dict):
                    row_valores = [row_valores.get(str(pc)) or row_valores.get(pc) for pc in piezas_cols]

                for v_item in row_valores:
                    v = v_item.get('val') if isinstance(v_item, dict) else v_item
                    needs_review = v_item.get('revision', False) if isinstance(v_item, dict) else False
                    
                    v_str = str(v).strip().upper().replace(',', '.') if v is not None else ''
                    
                    if any(v_str.startswith(x) for x in ['OK', 'ACEP', 'PAS']) or v_str == 'P': 
                        processed_vals.append({'val': v if v is not None else '', 'ok': True, 'review': needs_review})
                    elif any(v_str.startswith(x) for x in ['NOK', 'RECH', 'FALL', 'FAIL']) or v_str == 'R': 
                        processed_vals.append({'val': v if v is not None else '', 'ok': False, 'review': needs_review})
                    else:
                        try:
                            nums = re.findall(r"[-+]?\d*\.\d+|\d+", v_str)
                            if nums: 
                                processed_vals.append({'val': v, 'ok': (min_v - 0.0001) <= float(nums[0]) <= (max_v + 0.0001), 'review': needs_review})
                            else: 
                                processed_vals.append({'val': v if v is not None else '', 'ok': True, 'review': needs_review})
                        except:
                            processed_vals.append({'val': v if v is not None else '', 'ok': True, 'review': needs_review})
                new_row = row.copy()
                new_row['valores'] = processed_vals
                valid_matrix.append(new_row)
            except Exception as ex: 
                print(f"[ERROR-TOL] {row.get('control')}: {ex}")
                valid_matrix.append(row)

        context = {
            'success': True,
            'filename': file_name,
            'header': header_info,
            'auto_matched': auto_matched,
            'piezas': piezas_cols,
            'matrix': valid_matrix,
            'header_json': json.dumps(header_info),
            'piezas_json': json.dumps(piezas_cols),
            'matrix_json': json.dumps(valid_matrix),
            'procesos': Proceso.objects.all().order_by('nombre'),
            'articulos': Articulo.objects.all().order_by('nombre'),
            'elementos': Elemento.objects.all().order_by('nombre'),
            'clientes': Cliente.objects.all().order_by('nombre'),
        }
        
    return render(request, 'mediciones/ocr_lector.html', context)

@csrf_exempt
def importar_datos_ocr(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            header, matrix, piezas_cols = data.get('header'), data.get('matrix'), data.get('piezas')
            if not header or not matrix: return JsonResponse({'status': 'error', 'message': 'Datos incompletos'}, status=400)

            proyecto_nombre = header.get('proyecto', 'OCR Import')
            op_numero = int(''.join(filter(str.isdigit, str(header.get('op', '0')))) or 0)
            proceso_id, articulo_id, elemento_id, cliente_id = data.get('proceso_id'), data.get('articulo_id'), data.get('elemento_id'), data.get('cliente_id')
            
            from .models import Proceso, Articulo, Elemento, Cliente
            
            def match_or_create(model, name_val):
                if not name_val: return None
                obj = model.objects.filter(nombre__iexact=name_val.strip()).first() or model.objects.filter(nombre__icontains=name_val.strip()[:10]).first()
                if not obj: obj = model.objects.create(nombre=name_val.strip())
                return obj.id

            if not cliente_id: cliente_id = match_or_create(Cliente, header.get('cliente'))
            if not articulo_id: articulo_id = match_or_create(Articulo, header.get('articulo'))
            if not proceso_id: proceso_id = match_or_create(Proceso, header.get('denominacion'))
            if not elemento_id: elemento_id = match_or_create(Elemento, header.get('operacion'))
            
            planilla = PlanillaMedicion.objects.filter(num_op=op_numero).first()
            created = False
            if not planilla:
                planilla = PlanillaMedicion.objects.create(num_op=op_numero, proyecto=proyecto_nombre, fecha_elaborador=timezone.now().date(), observaciones='Importado automáticamente via OCR')
                created = True
            else:
                if proyecto_nombre and (not planilla.proyecto or planilla.proyecto == 'OCR Import'): planilla.proyecto = proyecto_nombre
            if not created:
                planilla.tolerancia_set.all().delete()
                ValorMedicion.objects.filter(planilla=planilla).delete()
            
            if proceso_id and str(proceso_id).isdigit(): planilla.proceso_id = int(proceso_id)
            if articulo_id and str(articulo_id).isdigit(): planilla.articulo_id = int(articulo_id)
            if elemento_id and str(elemento_id).isdigit(): planilla.elemento_id = int(elemento_id)
            if cliente_id and str(cliente_id).isdigit(): planilla.cliente_id = int(cliente_id)
            planilla.save()

            for i, row in enumerate(matrix):
                raw_control = row.get('control', '').strip()
                if not raw_control: continue
                control_nombre = re.sub(r'^\d+[\.\)\-\s]+', '', raw_control).strip().replace(']', '').replace('[', '').replace('|', '').strip()
                control = Control.objects.filter(nombre__iexact=control_nombre).first() or Control.objects.create(nombre=control_nombre)

                valores = row.get('valores', [])
                has_pnp_values = any(any(str(v.get('val') if isinstance(v, dict) else v).strip().upper().startswith(x) for x in ['OK', 'PAS', 'ACEP', 'NOK', 'FAL', 'FAI']) for v in valores)
                if has_pnp_values and not control.pnp: control.pnp = True; control.save()

                try:
                    nom_str = str(row.get('nominal', '0')).replace(',', '.')
                    nom_nums = re.findall(r"[-+]?\d*\.\d+|\d+", re.sub(r'\(?\d+[xX]\)?', '', nom_str).strip()) or re.findall(r"[-+]?\d*\.\d+|\d+", nom_str)
                    nominal_val = float(nom_nums[0]) if nom_nums else 0.0
                    tol_str_clean = re.sub(r'([-+])\s+(\d)', r'\1\2', str(row.get('tolerancia', '')).replace(',', '.').strip())
                    limit_max = limit_min = 0.0
                    
                    if '±' in tol_str_clean:
                        vals = re.findall(r"\d*\.?\d+", tol_str_clean)
                        if vals: limit_max = abs(float(vals[0])); limit_min = -abs(float(vals[0]))
                    else:
                        floats = [float(m) for m in re.findall(r"[-+]?\d*\.?\d+", tol_str_clean) if m not in ['.', '-', '+']]
                        if len(floats) >= 2: limit_max, limit_min = max(floats), min(floats)
                        elif len(floats) == 1:
                            val = floats[0]
                            if '+' not in tol_str_clean and '-' not in tol_str_clean:
                                limit_max = abs(val)
                                limit_min = -abs(val)
                            else:
                                limit_max = val if '+' in tol_str_clean and val > 0 else 0.0
                                limit_min = val if '-' in tol_str_clean and val < 0 else (-abs(val) if val != 0 else 0.0)
                except: nominal_val = limit_max = limit_min = 0.0

                instrumento_nombre = row.get('instrumento', '').strip()
                instrumento_obj = None
                if instrumento_nombre:
                    instrumento_obj = Instrumento.objects.filter(codigo__iexact=instrumento_nombre).first() or Instrumento.objects.filter(nombre__iexact=instrumento_nombre).first() or Instrumento.objects.create(nombre=instrumento_nombre, codigo=instrumento_nombre, tipo='OTRO')

                tolerancia, _ = Tolerancia.objects.update_or_create(planilla=planilla, control=control, defaults={'nominal': nominal_val, 'minimo': limit_min, 'maximo': limit_max, 'posicion': i + 1, 'instrumento': instrumento_obj})
                limit = min(len(valores), len(piezas_cols))
                
                for idx in range(limit):
                    pieza_num = piezas_cols[idx]
                    val_raw = valores[idx].get('val') if isinstance(valores[idx], dict) else valores[idx]
                    if val_raw is None or str(val_raw).strip() == '': continue

                    try:
                        val_float = val_pnp = None
                        val_clean = str(val_raw).strip().upper().replace(']', '').replace('[', '').replace('|', '')
                        if any(val_clean.startswith(x) for x in ['OK', 'PAS', 'ACEP']) or val_clean == 'P': val_pnp = 'OK'
                        elif any(val_clean.startswith(x) for x in ['NOK', 'FAL', 'FAI', 'RECH']) or val_clean == 'R': val_pnp = 'NOK'
                        else:
                            val_numeric_str = re.sub(r'[^\d\.\,]', '', str(val_raw)).replace(',', '.')
                            if val_numeric_str:
                                val_float = float(val_numeric_str)
                                min_l, max_l = tolerancia.get_absolute_limits()
                                if min_l is not None and max_l is not None:
                                    if min_l != 0.0 or max_l != 0.0:
                                        if val_float < (min_l - max(max_l-min_l, 0.5)*4) or val_float > (max_l + max(max_l-min_l, 0.5)*4): continue
                                    val_pnp = 'OK' if min_l <= val_float <= max_l else 'NOK'
                                else: val_pnp = 'OK'
                            else: continue

                        if val_pnp is not None or val_float is not None:
                            ValorMedicion.objects.update_or_create(planilla=planilla, control=control, pieza=pieza_num, defaults={'tolerancia': tolerancia, 'valor_pieza': val_float, 'valor_pnp': val_pnp, 'op': str(planilla.num_op)})
                    except: continue
            return JsonResponse({'status': 'success', 'message': f'Datos importados correctamente a la OP {op_numero}', 'op': op_numero, 'proy': planilla.proyecto, 'proc_id': planilla.proceso_id})
        except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

@login_required
@csrf_exempt
def configuracion_sistema(request):
    from .models import SystemConfig
    
    # Obtener o crear el registro global para la API Key de Groq, fallback a ANTHROPIC/GEMINI
    db_config, created = SystemConfig.objects.get_or_create(key="GROQ_API_KEY", defaults={"value": ""})
    if not db_config.value:
        ant_config = SystemConfig.objects.filter(key="ANTHROPIC_API_KEY").first()
        if ant_config and ant_config.value:
            db_config.value = ant_config.value
            db_config.save()
        else:
            gemini_config = SystemConfig.objects.filter(key="GEMINI_API_KEY").first()
            if gemini_config and gemini_config.value:
                db_config.value = gemini_config.value
                db_config.save()
            
    current_key = db_config.value or ""
            
    if request.method == 'POST':
        api_key = request.POST.get('api_key', '').strip()
        gemini_model = request.POST.get('gemini_model_name', 'llama-3.2-90b-vision-preview').strip()
        alerta_dias = request.POST.get('alerta_dias', '15')
        
        # Diagnóstico: imprimir exactamente lo que llega del formulario
        print(f"[CONFIG] POST recibido. api_key longitud={len(api_key)}, primeros 10 chars='{api_key[:10]}', últimos 6='{api_key[-6:] if len(api_key) >= 6 else api_key}'")
        
        # Guardar el valor directamente de lo ingresado en el formulario
        db_config.value = api_key
        db_config.save()
        
        # Guardar espejos por compatibilidad
        SystemConfig.objects.update_or_create(key="ANTHROPIC_API_KEY", defaults={"value": api_key})
        SystemConfig.objects.update_or_create(key="GEMINI_API_KEY", defaults={"value": api_key})
        print(f"[CONFIG] Guardado en BD. Valor confirmado: longitud={len(db_config.value)}")
        
        # Actualizar la variable de entorno del proceso
        if api_key:
            os.environ['GROQ_API_KEY'] = api_key
            os.environ['ANTHROPIC_API_KEY'] = api_key
            os.environ['GEMINI_API_KEY'] = api_key
        else:
            if 'GROQ_API_KEY' in os.environ:
                del os.environ['GROQ_API_KEY']
            if 'ANTHROPIC_API_KEY' in os.environ:
                del os.environ['ANTHROPIC_API_KEY']
            if 'GEMINI_API_KEY' in os.environ:
                del os.environ['GEMINI_API_KEY']
            
        user_profile = request.user.profile
        user_profile.gemini_model_name = gemini_model
        # Espejar en perfil de usuario por compatibilidad
        user_profile.gemini_api_key = api_key
        try: 
            user_profile.alerta_calibracion_dias = int(alerta_dias)
        except ValueError: 
            pass
            
        user_profile.save()
        messages.success(request, 'Configuración del sistema guardada exitosamente.')
        return redirect('configuracion_sistema')
    
    return render(request, 'mediciones/configuracion.html', {
        'current_key': current_key
    })