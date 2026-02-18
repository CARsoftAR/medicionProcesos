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
import datetime
import re

def supervisor_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        # Check if user has Calidad role or is superuser
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
        # Prevent non-supervisors from changing their own role in profile
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
        # For new users, password should be required
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
    
    # Filter parameters
    q = request.GET.get('q', '').strip()
    
    # Querysets
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
        # Filter values based on the filtered OPs for stats
        valores_qs = valores_qs.filter(
            Q(op__icontains=q) | 
            Q(planilla__proyecto__icontains=q)
        )
        is_filtered = True

    # List for the table (limited if not searching, or more if searching)
    limit = 15 if not q else 50
    planillas = planillas_qs[:limit]
    
    # Metrics for Dashboard
    hoy = timezone.now()
    hace_30_dias = hoy - timedelta(days=30)
    
    total_ops = planillas_qs.count()
    
    # Current values (30 days if global, or all if specific OP)
    if is_filtered:
        mediciones_base = valores_qs
    else:
        mediciones_base = valores_qs.filter(fecha__gte=hace_30_dias)

    mediciones_recientes = mediciones_base.count()
    
    # Global OK/NOK counts
    ok_count = mediciones_base.filter(valor_pnp='OK').count()
    nok_count = mediciones_base.filter(valor_pnp='NOK').count()
    
    # Data for Trend Chart (last 7 days - or specific periods if filtered)
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

    # Active alerts for instruments (excluding obsolete)
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
        # Handles the "Assign Controls" form submission
        selected_controls = request.POST.getlist('controles')
        if selected_controls:
            # We assign a default Tolerancia for each selected Control
            # "Posicion" is just a sequential order
            current_count = Tolerancia.objects.filter(planilla=planilla).count()
            for index, control_id in enumerate(selected_controls):
                control = Control.objects.get(id=control_id)
                Tolerancia.objects.create(
                    planilla=planilla,
                    control=control,
                    posicion=current_count + index + 1
                    # Nominal, Min, Max are left empty for the next step
                )
            messages.success(request, 'Controles asignados correctamente.')
            return redirect('asignar_tolerancias', planilla_id=planilla.id)
        else:
            messages.warning(request, 'Debe seleccionar al menos un control.')

    # Get available controls and currently assigned controls
    # assigned_ids = Tolerancia.objects.filter(planilla=planilla).values_list('control_id', flat=True)
    # available_controls = Control.objects.exclude(id__in=assigned_ids)
    
    # Simpler approach: Display all, user selects relevant ones. 
    # Or, list existing ones (to remove?) and available ones (to add).
    # Based on image "Crear Procesos", it seems we just pick from valid controls.
    
    # Let's show currently assigned controls on one side, and available on the other (or a single list to check)
    assigned_tolerancias = Tolerancia.objects.filter(planilla=planilla).select_related('control')
    all_controls = Control.objects.all() # In a real app, maybe filter by relevance?
    
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
        # Batch update of tolerances
        for tolerancia in tolerancias:
            if tolerancia.control.pnp:
                continue # PnP doesn't have numeric limits in this step usually (or handled differently)
            
            # IDs in form are like "min_123", "max_123", "nom_123" where 123 is tolerancia.id
            nom = request.POST.get(f'nominal_{tolerancia.id}')
            min_val = request.POST.get(f'min_{tolerancia.id}')
            max_val = request.POST.get(f'max_{tolerancia.id}')
            
            # Simple validation/cleaning could go here
            if nom: tolerancia.nominal = nom
            if min_val: tolerancia.minimo = min_val
            if max_val: tolerancia.maximo = max_val
            tolerancia.save()
            
        messages.success(request, 'Tolerancias guardadas correctamente.')
        return redirect(f"{reverse('nueva_medicion_op')}?proy={planilla.proyecto}&op={planilla.num_op}&proc={planilla.proceso.id}")

    context = {
        'planilla': planilla,
        'tolerancias': tolerancias
    }
    return render(request, 'mediciones/asignar_tolerancias.html', context)

@login_required
def ingreso_mediciones(request, planilla_id):
    planilla = get_object_or_404(PlanillaMedicion, id=planilla_id)
    return redirect(f"{reverse('nueva_medicion_op')}?proy={planilla.proyecto}&op={planilla.num_op}&proc={planilla.proceso.id}")

def OLD_ingreso_mediciones(request, planilla_id):
        
    valores_existentes = ValorMedicion.objects.filter(planilla=planilla, pieza=pieza_actual)
    valores_dict = { v.control_id: v for v in valores_existentes }
    
    rows = []
    for tol in tolerancias:
        val_obj = valores_dict.get(tol.control.id)
        current_val = None
        status = 'PENDIENTE'
        
        if val_obj:
            if tol.control.pnp:
                current_val = val_obj.valor_pnp
                status = 'OK' if current_val == 'OK' else 'NOK'
                if current_val is None: status = 'PENDIENTE'
            else:
                current_val = val_obj.valor_pieza
                if current_val is not None:
                    try:
                         # Logic from Specification: LI = Vn - Tmin, LS = Vn + Tmax
                         val_f = float(current_val)
                         nominal_f = float(tol.nominal) if tol.nominal else 0.0
                         min_dev = float(tol.minimo) if tol.minimo is not None else 0.0
                         max_dev = float(tol.maximo) if tol.maximo is not None else 0.0
                         
                         min_limit = nominal_f - min_dev
                         max_limit = nominal_f + max_dev
                         
                         if val_f < min_limit or val_f > max_limit: 
                             status = 'NOK'
                         else: 
                             status = 'OK'
                    except:
                        status = 'ERROR'
        
        rows.append({
            'tolerancia': tol,
            'valor': current_val,
            'status': status
        })

    context = {
        'planilla': planilla,
        'pieza_actual': pieza_actual,
        'rows': rows,
        'next_pieza': pieza_actual + 1,
        'prev_pieza': pieza_actual - 1 if pieza_actual > 1 else None
    }
    return render(request, 'mediciones/ingreso_mediciones.html', context)

@supervisor_required
def api_create_master(request, model_name):
    if request.method == 'POST':
        name = request.POST.get('nombre')
        if not name:
            return JsonResponse({'status': 'error', 'message': 'Nombre es requerido'}, status=400)
        
        try:
            if model_name == 'cliente':
                obj = Cliente.objects.create(nombre=name)
            elif model_name == 'articulo':
                obj = Articulo.objects.create(nombre=name)
            elif model_name == 'proceso':
                obj = Proceso.objects.create(nombre=name)
            elif model_name == 'elemento':
                obj = Elemento.objects.create(nombre=name)
            elif model_name == 'control':
                 # Check for duplicates
                 if Control.objects.filter(nombre__iexact=name).exists():
                     return JsonResponse({'status': 'error', 'message': f'El control "{name}" ya existe.'}, status=400)
                 
                 # Special case for controls which have extra fields, but for quick add name is enough
                 is_pnp = request.POST.get('pnp') == 'true'
                 obj = Control.objects.create(nombre=name, pnp=is_pnp)
            elif model_name == 'maquina':
                 obj = Maquina.objects.create(nombre=name)
            elif model_name == 'instrumento':
                 obj = Instrumento.objects.create(nombre=name)
            else:
                return JsonResponse({'status': 'error', 'message': 'Modelo inválido'}, status=400)
            
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

from django.core.paginator import Paginator

@login_required
def lista_procesos(request):
    # Get per_page from request or session, default to 10
    per_page = request.GET.get('per_page')
    if per_page:
        request.session['procesos_per_page'] = per_page
    else:
        per_page = request.session.get('procesos_per_page', 10)
    
    procesos_list = Proceso.objects.all().order_by('nombre')
    paginator = Paginator(procesos_list, per_page)
    
    page_number = request.GET.get('page')
    procesos = paginator.get_page(page_number)
    
    return render(request, 'mediciones/lista_procesos.html', {
        'procesos': procesos,
        'per_page': int(per_page)
    })

@supervisor_required
def crear_proceso(request):
    if request.method == 'POST':
        form = ProcesoForm(request.POST)
        if form.is_valid():
            form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success'})
            messages.success(request, 'Proceso creado correctamente.')
            return redirect('lista_procesos')
    else:
        form = ProcesoForm()
    
    return render(request, 'mediciones/crear_proceso.html', {'form': form, 'titulo': 'Nuevo Proceso'})

@supervisor_required
def editar_proceso(request, pk):
    proceso = get_object_or_404(Proceso, pk=pk)
    if request.method == 'POST':
        form = ProcesoForm(request.POST, instance=proceso)
        if form.is_valid():
            form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success', 'edit': True})
            messages.success(request, 'Proceso actualizado correctamente.')
            return redirect('lista_procesos')
    else:
        form = ProcesoForm(instance=proceso)
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
    if per_page:
        request.session['clientes_per_page'] = per_page
    else:
        per_page = request.session.get('clientes_per_page', 10)
    
    clientes_list = Cliente.objects.all().order_by('nombre')
    paginator = Paginator(clientes_list, per_page)
    
    page_number = request.GET.get('page')
    clientes = paginator.get_page(page_number)
    
    return render(request, 'mediciones/lista_clientes.html', {
        'clientes': clientes,
        'per_page': int(per_page)
    })

@supervisor_required
def crear_cliente(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cliente creado correctamente.')
            return redirect('lista_clientes')
    else:
        form = ClienteForm()
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
    else:
        form = ClienteForm(instance=cliente)
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
    if per_page:
        request.session['elementos_per_page'] = per_page
    else:
        per_page = request.session.get('elementos_per_page', 10)
    
    elementos_list = Elemento.objects.all().order_by('nombre')
    paginator = Paginator(elementos_list, per_page)
    
    page_number = request.GET.get('page')
    elementos = paginator.get_page(page_number)
    
    return render(request, 'mediciones/lista_elementos.html', {
        'elementos': elementos,
        'per_page': int(per_page)
    })

@supervisor_required
def crear_elemento(request):
    if request.method == 'POST':
        form = ElementoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Elemento creado correctamente.')
            return redirect('lista_elementos')
    else:
        form = ElementoForm()
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
    else:
        form = ElementoForm(instance=elemento)
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
    # Get per_page from request or session, default to 10
    per_page = request.GET.get('per_page')
    if per_page:
        request.session['controles_per_page'] = per_page
    else:
        per_page = request.session.get('controles_per_page', 10)
    
    controles_list = Control.objects.all().order_by('nombre')
    paginator = Paginator(controles_list, per_page)
    
    page_number = request.GET.get('page')
    controles = paginator.get_page(page_number)
    
    return render(request, 'mediciones/lista_controles.html', {
        'controles': controles,
        'per_page': int(per_page)
    })

@supervisor_required
def crear_control(request):
    if request.method == 'POST':
        form = ControlForm(request.POST)
        if form.is_valid():
            form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success'})
            messages.success(request, 'Control creado correctamente.')
            return redirect('lista_controles')
        elif request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Extract the first error message
            error_msg = next(iter(form.errors.values()))[0]
            return JsonResponse({'status': 'error', 'message': error_msg})
    else:
        form = ControlForm()
    
    return render(request, 'mediciones/crear_control.html', {'form': form, 'titulo': 'Nuevo Control'})

@supervisor_required
def editar_control(request, pk):
    control = get_object_or_404(Control, pk=pk)
    if request.method == 'POST':
        form = ControlForm(request.POST, instance=control)
        if form.is_valid():
            form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success', 'edit': True})
            messages.success(request, 'Control actualizado correctamente.')
            return redirect('lista_controles')
        elif request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            error_msg = next(iter(form.errors.values()))[0]
            return JsonResponse({'status': 'error', 'message': error_msg})
    else:
        form = ControlForm(instance=control)
    return render(request, 'mediciones/crear_control.html', {'form': form, 'titulo': 'Editar Control', 'is_edit': True})

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
    if per_page:
        request.session['instrumentos_per_page'] = per_page
    else:
        per_page = request.session.get('instrumentos_per_page', 10)
    
    instrumentos_list = Instrumento.objects.all().order_by('nombre')
    
    # Filters
    search = request.GET.get('search')
    if search:
        instrumentos_list = instrumentos_list.filter(
            models.Q(nombre__icontains=search) | 
            models.Q(codigo__icontains=search) |
            models.Q(marca__icontains=search)
        )
    
    filter_type = request.GET.get('filter')
    if filter_type == 'alertas':
        # Filter instruments that are either expired OR in alert state
        from datetime import date
        today = date.today()
        # We use a list comprehension because is_en_alerta depends on instance attributes (alerta_dias)
        # However, we can approximate it with a wide Q filter for performance if needed.
        # For now, let's filter the queryset based on proxima_calibracion.
        # A conservative approach: proxima_calibracion <= today + 60 days (max alert typically)
        # OR just filter the list and re-queryset.
        ids_vencidos = [i.id for i in instrumentos_list if i.is_calibracion_vencida() or i.is_en_alerta()]
        instrumentos_list = instrumentos_list.filter(id__in=ids_vencidos)

    paginator = Paginator(instrumentos_list, per_page)
    page_number = request.GET.get('page')
    instrumentos = paginator.get_page(page_number)
    
    return render(request, 'mediciones/lista_instrumentos.html', {
        'instrumentos': instrumentos,
        'per_page': int(per_page),
        'search': search
    })

@supervisor_required
def crear_instrumento(request):
    if request.method == 'POST':
        form = InstrumentoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Instrumento creado correctamente.')
            return redirect('lista_instrumentos')
    else:
        form = InstrumentoForm()
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
    else:
        form = InstrumentoForm(instance=instrumento)
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
    return render(request, 'mediciones/detalle_instrumento.html', {
        'instrumento': instrumento,
        'historial': historial
    })

@csrf_exempt
@supervisor_required
def registrar_calibracion_ajax(request):
    if request.method == 'POST':
        from datetime import datetime
        from dateutil.relativedelta import relativedelta
        try:
            # Handle both JSON and FormData
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
            
            # Create History
            HistorialCalibracion.objects.create(
                instrumento=instrumento,
                fecha_calibracion=fecha,
                resultado=resultado,
                certificado_nro=certificado,
                archivo_certificado=archivo,
                observaciones=obs,
                usuario=request.user
            )
            
            # Update Instrument
            if resultado == 'APROBADO':
                instrumento.ultima_calibracion = fecha
                instrumento.certificado_nro = certificado
                instrumento.proxima_calibracion = fecha + relativedelta(months=instrumento.frecuencia_meses)
                instrumento.en_servicio = True
            else:
                instrumento.en_servicio = False
                
            instrumento.save()
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
@supervisor_required
def dashboard_calibracion(request):
    # Base Query: Active items (not obsolete)
    activos = Instrumento.objects.filter(es_obsoleto=False)
    
    # Active Stats
    vencidos_count = len([i for i in activos if i.is_calibracion_vencida()])
    alerta_count = len([i for i in activos if i.is_en_alerta()])
    ok_count = len([i for i in activos if not i.is_calibracion_vencida() and not i.is_en_alerta() and i.en_servicio])
    
    # Ownership Stats
    propios_count = activos.filter(es_propio=True).count()
    clientes_count = activos.filter(es_propio=False).count()
    obsoletos_count = Instrumento.objects.filter(es_obsoleto=True).count()
    
    # Detailed counts
    fuera_servicio_count = activos.filter(en_servicio=False).count()
    
    # Stats by type (only for active)
    tipos_count = {}
    for choice in Instrumento.TIPO_CHOICES:
        count = activos.filter(tipo=choice[0]).count()
        if count > 0:
            tipos_count[choice[1]] = count
            
    # List: Next calibrations (prioritizing overdue and warning)
    prox_calibraciones = activos.order_by('proxima_calibracion')[:15]
    
    return render(request, 'mediciones/dashboard_calibracion.html', {
        'vencidos_count': vencidos_count,
        'alerta_count': alerta_count,
        'ok_count': ok_count,
        'fuera_servicio_count': fuera_servicio_count,
        'propios_count': propios_count,
        'clientes_count': clientes_count,
        'obsoletos_count': obsoletos_count,
        'tipos_count': tipos_count,
        'prox_calibraciones': prox_calibraciones,
    })

@supervisor_required
def lista_estructuras(request):
    # Unique structures grouped by num_op and proyecto
    planillas = PlanillaMedicion.objects.all().order_by('-id')
    
    unique_structures = []
    seen = set()
    
    for p in planillas:
        # Use tuple as key to identify unique projects
        key = (p.num_op, p.proyecto)
        if key not in seen:
            unique_structures.append(p)
            seen.add(key)
            
    return render(request, 'mediciones/lista_estructuras.html', {
        'estructuras': unique_structures
    })

@supervisor_required
def eliminar_estructura(request):
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            proyecto = data.get('proyecto')
            num_op = data.get('num_op')
            
            # Build filters
            filters = {}
            if proyecto:
                filters['proyecto'] = proyecto
            if num_op:
                filters['num_op'] = num_op
                
            if not filters:
                 return JsonResponse({'status': 'error', 'message': 'Faltan parámetros de identificación.'})

            deleted_count, _ = PlanillaMedicion.objects.filter(**filters).delete()
            
            if deleted_count > 0:
                messages.success(request, 'Estructura eliminada correctamente.')
                return JsonResponse({'status': 'success', 'message': 'Estructura eliminada.'})
            else:
                return JsonResponse({'status': 'error', 'message': 'No se encontró la estructura para eliminar.'})
                
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
            
    return JsonResponse({'status': 'error', 'message': 'Método no permitido.'})

@supervisor_required
def configurar_estructura(request):
    # Check if we are editing
    edit_op = request.GET.get('op')
    edit_proy = request.GET.get('proy')
    
    existing_data = None
    if edit_op or edit_proy:
        # Load existing structure
        filters = {}
        if edit_op: filters['num_op'] = edit_op
        if edit_proy: filters['proyecto'] = edit_proy
        
        # Remove select_related to rely on direct access/lazy loading for debugging
        related_planillas = PlanillaMedicion.objects.filter(**filters)
        if related_planillas.exists():
            first = related_planillas[0]
            existing_data = {
                'cliente_id': first.cliente_id,
                'proyecto': first.proyecto,
                'articulo_id': first.articulo_id,
                'num_op': first.num_op,
                'procesos': []
            }
            # Add processes and their tolerances
            for p in related_planillas:
                if p.proceso_id is None:
                    continue

                # Robust name retrieval
                p_nombre = 'Sin Proceso'
                try:
                    if p.proceso:
                        p_nombre = p.proceso.nombre
                    elif p.proceso_id:
                        # Fallback: Manual fetch
                        p_obj = Proceso.objects.get(pk=p.proceso_id)
                        p_nombre = p_obj.nombre
                except Exception:
                     # Fallback if both fail
                    p_nombre = f"Proceso {p.proceso_id}"

                e_nombre = ''
                try:
                    if p.elemento:
                        e_nombre = p.elemento.nombre
                    elif p.elemento_id:
                         e_obj = Elemento.objects.get(pk=p.elemento_id)
                         e_nombre = e_obj.nombre
                except Exception:
                    if p.elemento_id:
                        e_nombre = f"Elemento {p.elemento_id}"

                p_info = {
                    'id': p.proceso_id,
                    'nombre': p_nombre,
                    'elemento_id': p.elemento_id if p.elemento_id else '',
                    'elemento_nombre': e_nombre,
                    'controles': []
                }
                tolerancias = Tolerancia.objects.filter(planilla=p).order_by('posicion')
                for t in tolerancias:
                    p_info['controles'].append({
                        'id': t.control_id,
                        'nombre': t.control.nombre,
                        'min': float(t.minimo) if t.minimo is not None else '',
                        'nom': float(t.nominal) if t.nominal is not None else '',
                        'max': float(t.maximo) if t.maximo is not None else ''
                    })
                existing_data['procesos'].append(p_info)

    if request.method == 'POST':
        import json
        try:
            data_json = request.POST.get('estructura_data')
            if not data_json:
                 return JsonResponse({'status': 'error', 'message': 'No se recibieron datos de estructura'}, status=400)
            
            data = json.loads(data_json)
            
            # Common Header
            cliente_id = data.get('cliente')
            proyecto = data.get('proyecto')
            articulo_id = data.get('articulo')
            num_op = data.get('num_op') or 0
            
            cliente = Cliente.objects.get(id=cliente_id) if cliente_id else None
            articulo = Articulo.objects.get(id=articulo_id) if articulo_id else None
            
            # --- SMART UPDATE STRATEGY ---
            # Instead of deleting everything, we fetch existing planillas to reuse them.
            # This preserves ids and linked measurements.
            
            existing_planillas = list(PlanillaMedicion.objects.filter(proyecto=proyecto, num_op=num_op))
            processed_planillas_ids = []

            procesos_data = data.get('procesos', [])
            
            # If no processes, we might still want a placeholder or just header info.
            # But usually we have processes.
            
            for p_data in procesos_data:
                proceso_id = p_data.get('id')
                proceso = Proceso.objects.get(id=proceso_id)
                
                # Resolve Elemento
                elemento_id = p_data.get('elemento_id')
                elemento = None
                if elemento_id:
                     try:
                        elemento = Elemento.objects.get(id=elemento_id)
                     except Elemento.DoesNotExist:
                        pass
                else:
                    elemento_nombre = p_data.get('elemento_nombre')
                    if elemento_nombre:
                        elemento, _ = Elemento.objects.get_or_create(nombre=elemento_nombre)

                # Try to find a matching existing planilla
                # Match criteria: same Proceso and same Elemento
                match_planilla = None
                for ep in existing_planillas:
                    if ep.proceso_id == int(proceso_id) and ep.elemento == elemento:
                        match_planilla = ep
                        break
                
                if match_planilla:
                    # UPDATE existing
                    match_planilla.cliente = cliente
                    match_planilla.articulo = articulo
                    # proyecto and num_op are assumed same since we filtered by them, 
                    # but if case sensitivity changed or whatever, let's set them.
                    match_planilla.proyecto = proyecto 
                    match_planilla.num_op = num_op
                    match_planilla.save()
                    planilla = match_planilla
                else:
                    # CREATE new
                    planilla = PlanillaMedicion.objects.create(
                        cliente=cliente,
                        proyecto=proyecto,
                        articulo=articulo,
                        proceso=proceso,
                        elemento=elemento,
                        num_op=num_op
                    )
                
                processed_planillas_ids.append(planilla.id)
                
                # --- SYNC TOLERANCES ---
                # Fetch existing tolerances for this planilla
                existing_tols = list(Tolerancia.objects.filter(planilla=planilla))
                processed_tol_ids = []
                
                controles_data = p_data.get('controles', [])
                for idx, c_data in enumerate(controles_data):
                    control_id = c_data.get('id')
                    try:
                        control = Control.objects.get(id=control_id)
                    except Control.DoesNotExist:
                        continue
                        
                    def to_decimal(val):
                        if val == '' or val is None: return None
                        try:
                            if isinstance(val, str):
                                val = val.replace(',', '.')
                            return float(val)
                        except:
                            return None

                    min_val = to_decimal(c_data.get('min'))
                    nom_val = to_decimal(c_data.get('nom'))
                    max_val = to_decimal(c_data.get('max'))

                    # Find matching tolerance by control
                    match_tol = None
                    for et in existing_tols:
                        if et.control_id == int(control_id):
                            match_tol = et
                            break
                    
                    if match_tol:
                        # Update
                        match_tol.minimo = min_val
                        match_tol.nominal = nom_val
                        match_tol.maximo = max_val
                        match_tol.posicion = idx + 1
                        match_tol.save()
                        processed_tol_ids.append(match_tol.id)
                    else:
                        # Create
                        new_tol = Tolerancia.objects.create(
                            planilla=planilla,
                            control=control,
                            minimo=min_val,
                            nominal=nom_val,
                            maximo=max_val,
                            posicion=idx + 1
                        )
                        processed_tol_ids.append(new_tol.id)
                
                # Delete removed tolerances (controls removed from UI for this process)
                # Note: ValorMedicion linked to these will have tolerance=NULL but won't be deleted 
                # (assuming on_delete is SET_NULL for tolerance, which it is)
                for et in existing_tols:
                    if et.id not in processed_tol_ids:
                        et.delete()

            # --- CLEANUP ORPHANED PLANILLAS ---
            # If a process block was removed from UI, we delete the corresponding PlanillaMedicion.
            # WARNING: This WILL delete associated ValorMedicion (CASCADE).
            # This follows the logic "if I remove it from structure, I don't want it".
            # The User's request was "if I add a control..., don't delete". 
            # So implicit existing stuff that IS in UI is saved above. Stuff NOT in UI is deleted.
            for ep in existing_planillas:
                if ep.id not in processed_planillas_ids:
                    ep.delete()
            
            return JsonResponse({
                'status': 'success', 
                'message': f'Estructura actualizada con éxito.',
                'redirect_url': reverse('lista_estructuras')
            })
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    # Context for GET
    clientes = Cliente.objects.all().order_by('nombre')
    articulos = Articulo.objects.all().order_by('nombre')
    procesos = Proceso.objects.all().order_by('nombre')
    controles = Control.objects.all().order_by('nombre')
    elementos = Elemento.objects.all().order_by('nombre')
    
    context = {
        'clientes': clientes,
        'articulos': articulos,
        'procesos_list': procesos,
        'elementos_list': elementos,
        'controles_list': controles,
        'existing_data': existing_data,
        'titulo': 'Editar Estructura' if existing_data else 'Configurar Estructura'
    }
    return render(request, 'mediciones/configurar_estructura.html', context)
@login_required
def nueva_medicion_op(request):
    from django.shortcuts import render, get_object_or_404, redirect
    from django.urls import reverse
    from django.contrib import messages
    from .models import PlanillaMedicion, Tolerancia, ValorMedicion, Proceso, Maquina, Instrumento

    proy_query = request.GET.get('proy', '').strip()
    op_query = request.GET.get('op', '').strip()
    proc_id = request.GET.get('proc', '').strip()
    pieza_actual = request.GET.get('pieza', 1)
    
    try:
        pieza_actual = int(str(pieza_actual).strip())
    except:
        pieza_actual = 1
        
    planilla = None
    rows = []
    piezas_medidas = []
    piezas_mostrar = []
    first_p = last_p = prev_p = next_p = None
    
    # 1. Selection logic
    if op_query:
        # Build filter dynamically
        filters = {}
        
        # Determine if OP looks like a number
        if op_query.isdigit():
            # Try both exact string match and integer match
            planillas = PlanillaMedicion.objects.filter(num_op=op_query)
            if not planillas.exists():
                planillas = PlanillaMedicion.objects.filter(num_op=int(op_query))
        else:
            planillas = PlanillaMedicion.objects.filter(num_op=op_query)

        # If project is provided, further narrow down
        if proy_query:
            planillas = planillas.filter(proyecto=proy_query)

        if proc_id and proc_id != 'None' and str(proc_id).isdigit():
            planillas = planillas.filter(proceso_id=proc_id)
            
        planillas = planillas.select_related('elemento', 'proceso', 'cliente', 'articulo')

        if planillas.exists():
            planilla = planillas.first() # For UI context
            
            # 2. Load Controls/Tolerances from ALL planillas found
            tolerancias = Tolerancia.objects.filter(planilla__in=planillas).select_related('control', 'planilla__elemento', 'planilla__proceso').order_by('planilla__elemento__nombre', 'posicion')
            
            # 3. Handle POST (Save measurements)
            if request.method == 'POST':
                # Machine Update (traceability)
                maquina_id = request.POST.get('maquina_id')
                if maquina_id:
                    planillas.update(maquina=maquina_id)

                for tol in tolerancias:
                    # Instrument Update (traceability per control)
                    instr_id = request.POST.get(f'instrumento_{tol.id}')
                    if instr_id:
                        tol.instrumento_id = instr_id
                        tol.save()

                    # Determine Input Value based on Type
                    if tol.control.pnp:
                        # PNP Logic
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
                        # Numeric Logic
                        val_input = request.POST.get(f'valor_{tol.id}')
                        if val_input is not None:
                            val_obj, _ = ValorMedicion.objects.update_or_create(
                                planilla=tol.planilla, control=tol.control, pieza=pieza_actual, tolerancia=tol,
                                defaults={'posicion': tol.posicion, 'op': str(tol.planilla.num_op) if tol.planilla.num_op else ''}
                            )
                            val_obj.valor_pnp = None
                            if val_input.strip() == '':
                                val_obj.valor_pieza = None
                            else:
                                try:
                                    clean_val = val_input.replace(',', '.')
                                    val_obj.valor_pieza = float(clean_val)
                                except:
                                    pass
                            val_obj.save()
                
                messages.success(request, f'Mediciones de Pieza {pieza_actual} guardadas.')
                if 'guardar_siguiente' in request.POST:
                    return redirect(f"{reverse('nueva_medicion_op')}?proy={proy_query}&op={op_query}&proc={proc_id}&pieza={pieza_actual + 1}")

            # 4. Load Existing Values for the Table
            # We filter by planillas__in=planillas to cover all elements
            valores_existentes = ValorMedicion.objects.filter(planilla__in=planillas, pieza=pieza_actual)
            # Use (planilla_id, control_id) as key because same control might exist in different elements
            valores_dict = { (v.planilla_id, v.control_id): v for v in valores_existentes }
            
            # 3. Handle POST (Save measurements)
            # ... (Existing POST logic logic is fine, keeping context)

            # --- INTELLIGENT SPC ALERTS ---
            from .utils_spc import SPCAnalyzer
            
            # Optimization: Only fetch history for controls visible on screen
            # AND Limit history to the current piece (and past) to avoid "future" alerts confusing the current view
            visible_control_ids = [t.control_id for t in tolerancias]
            
            history_dict = {}
            all_history = ValorMedicion.objects.filter(
                planilla__in=planillas,
                control_id__in=visible_control_ids,
                pieza__lte=pieza_actual  # Stop at current piece so "Last Value" == Current Piece Value
            ).order_by('pieza')
            
            for v in all_history:
                # Primary Key: Tolerancia ID (Specific Row)
                # Fallback: (Planilla, Control) (Legacy/Generic)
                if v.tolerancia_id:
                    key = f"tol_{v.tolerancia_id}"
                else:
                    key = f"pc_{v.planilla_id}_{v.control_id}"
                
                if key not in history_dict:
                    history_dict[key] = []
                if v.valor_pieza is not None:
                    history_dict[key].append(float(v.valor_pieza))

            for tol in tolerancias:
                val_obj = valores_dict.get((tol.planilla_id, tol.control_id))
                current_val = None
                status = 'PENDIENTE'
                
                # Run SPC Analysis
                spc_alerts = []
                if not tol.control.pnp:
                    min_limit, max_limit = tol.get_absolute_limits()
                    
                    # Try fetch by Integrity-Safe ID (Tolerancia) first, then fallback
                    h_values = history_dict.get(f"tol_{tol.id}", [])
                    if not h_values:
                        h_values = history_dict.get(f"pc_{tol.planilla_id}_{tol.control_id}", [])

                    analyzer = SPCAnalyzer(h_values, nominal=tol.nominal, min_limit=min_limit, max_limit=max_limit)
                    nelson_violations = analyzer.check_nelson_rules()
                    
                    # Last point index in history
                    last_idx = len(h_values) - 1
                    
                    for v in nelson_violations:
                        # Only show alerts that involve the current/last point to avoid noise
                        if v['point'] == last_idx:
                            spc_alerts.append({
                                'message': f"📍 {tol.control.nombre}: {v['desc']}",
                                'severity': v['severity']
                            })
                
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
                                
                                is_ok = True
                                if min_limit is not None and val_f < min_limit: is_ok = False
                                if max_limit is not None and val_f > max_limit: is_ok = False
                                
                                if not is_ok:
                                    status = 'NOK'
                                else: 
                                    status = 'OK'
                            except:
                                status = 'ERROR'
                
                rows.append({
                    'tolerancia': tol,
                    'valor': current_val,
                    'status': status,
                    'spc_alerts': spc_alerts,
                    'has_warning': any(a['severity'] == 'warning' for a in spc_alerts),
                    'has_danger': any(a['severity'] == 'danger' for a in spc_alerts)
                })

            # Use the first planilla for header info (Project, OP, Proceso)
            planilla = planillas.first()

        # 5. Piece Navigation Info - Look across ALL relevant planillas for this OP/Project
        piezas_medidas = ValorMedicion.objects.filter(planilla__in=planillas).values_list('pieza', flat=True).distinct().order_by('pieza')
        max_p = piezas_medidas.last() if piezas_medidas.exists() else 0
        
        # range_piezas is the sorted unique list of pieces with measurements + next one
        range_piezas = list(piezas_medidas)
        if (max_p + 1) not in range_piezas:
            range_piezas.append(max_p + 1)
        
        # Paginator logic for pieces
        try:
            p_actual_int = int(pieza_actual)
            current_idx = range_piezas.index(p_actual_int) if p_actual_int in range_piezas else -1
        except:
            current_idx = -1
            
        # Navigation helpers
        first_p = range_piezas[0] if range_piezas else 1
        last_p = range_piezas[-1] if range_piezas else 1
        prev_p = range_piezas[current_idx - 1] if current_idx > 0 else None
        next_p = range_piezas[current_idx + 1] if current_idx != -1 and current_idx < len(range_piezas) - 1 else None
        
        # Window of 4 pieces to show
        window_size = 4
        if len(range_piezas) <= window_size:
            piezas_mostrar = range_piezas
        else:
            if current_idx == -1: # Not in list (maybe manual entry not saved yet)
                piezas_mostrar = range_piezas[:window_size]
            else:
                start = max(0, current_idx - 1)
                end = start + window_size
                if end > len(range_piezas):
                    end = len(range_piezas)
                    start = max(0, end - window_size)
                piezas_mostrar = range_piezas[start:end]

    # Context for selection and data display
    proyectos = PlanillaMedicion.objects.values_list('proyecto', flat=True).distinct().order_by('proyecto')
    
    ops_disponibles = []
    if proy_query:
        # Get OPs for this project
        ops_disponibles = PlanillaMedicion.objects.filter(proyecto=proy_query).values_list('num_op', flat=True).distinct().order_by('num_op')

    procesos_disponibles = []
    if proy_query and op_query:
        # Find processes for this Project AND OP
        p_ids = PlanillaMedicion.objects.filter(proyecto=proy_query, num_op=op_query).values_list('proceso_id', flat=True).distinct()
        procesos_disponibles = Proceso.objects.filter(id__in=p_ids).order_by('nombre')

    context = {
        'proyectos': proyectos,
        'ops_disponibles': ops_disponibles,
        'procesos_disponibles': procesos_disponibles,
        'query_proy': proy_query,
        'query_op': int(op_query) if op_query and op_query.isdigit() else op_query,
        'query_proc': int(proc_id) if proc_id and proc_id != 'None' and proc_id.isdigit() else None,
        'planilla': planilla,
        'rows': rows,
        'pieza_actual': pieza_actual,
        'piezas_medidas': list(piezas_medidas) if planilla else [],
        'piezas_navegacion': piezas_mostrar if planilla else [],
        'first_p': first_p if planilla else None,
        'last_p': last_p if planilla else None,
        'prev_p': prev_p if planilla else None,
        'next_p': next_p if planilla else None,
        'maquinas': Maquina.objects.all(),
        'instrumentos': Instrumento.objects.all(),
        'titulo': 'Ingreso de Mediciones'
    }
    return render(request, 'mediciones/nueva_medicion_op.html', context)
@csrf_exempt
@login_required
def guardar_medicion_ajax(request):
    if request.method == 'POST':
        import json
        import logging
        logger = logging.getLogger(__name__)
        
        data = json.loads(request.body)
        
        tol_id = data.get('tolerancia_id')
        pieza = data.get('pieza')
        valor = data.get('valor')
        
        logger.info(f"AJAX Save - Received: tol_id={tol_id}, pieza={pieza}, valor='{valor}' (type: {type(valor)})")
        
        try:
            tol = Tolerancia.objects.get(id=tol_id)
            pieza_int = int(str(pieza))
            
            val_obj, created = ValorMedicion.objects.update_or_create(
                planilla=tol.planilla,
                control=tol.control,
                pieza=pieza_int,
                defaults={
                    'tolerancia': tol,
                    'posicion': tol.posicion,
                    'op': str(tol.planilla.num_op) if tol.planilla.num_op else ''
                }
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
                        
                        # Calculate OK/NOK status for the dashboard
                        min_l, max_l = tol.get_absolute_limits()
                        if min_l is not None and max_l is not None:
                            if min_l <= val_num <= max_l:
                                val_obj.valor_pnp = 'OK'
                            else:
                                val_obj.valor_pnp = 'NOK'
                        else:
                            val_obj.valor_pnp = 'OK' # If no limits, assume OK if value exists
                            
                        logger.info(f"AJAX Save - Converted '{valor}' -> {val_obj.valor_pieza}, Status: {val_obj.valor_pnp}")
                    except Exception as conv_err:
                        logger.error(f"AJAX Save - Conversion failed: {conv_err}")
                        val_obj.valor_pieza = None
                        val_obj.valor_pnp = 'NOK'
                else:
                    val_obj.valor_pieza = None
                    val_obj.valor_pnp = None
            
            val_obj.save()
            logger.info(f"AJAX Save - Saved: valor_pieza={val_obj.valor_pieza}")
            
            return JsonResponse({
                'status': 'success',
                'saved_value': val_obj.valor_pieza if not tol.control.pnp else val_obj.valor_pnp
            })
        except Exception as e:
            logger.error(f"AJAX Save - Error: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
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
        
        # Robust filtering matching main view logic
        if op.isdigit():
            q = PlanillaMedicion.objects.filter(proyecto=proy, num_op=op)
            if not q.exists():
                q = PlanillaMedicion.objects.filter(proyecto=proy, num_op=int(op))
        else:
            q = PlanillaMedicion.objects.filter(proyecto=proy, num_op=op)
            
        if proc_id and proc_id != 'None' and str(proc_id).isdigit():
            q = q.filter(proceso_id=proc_id)
            
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
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
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
            
            if not proy or not op or not pieza:
                return JsonResponse({'status': 'error', 'message': 'Faltan parámetros'}, status=400)

            # --- Robust Filtering Logic (matching nueva_medicion_op) ---
            planillas = PlanillaMedicion.objects.filter(proyecto=proy, num_op=op)
            
            # If OP might be int vs string
            if not planillas.exists() and str(op).isdigit():
                 planillas = PlanillaMedicion.objects.filter(proyecto=proy, num_op=int(op))
            
            # Optional Process Filter
            if proc_id and str(proc_id).isdigit():
                planillas = planillas.filter(proceso_id=proc_id)
            
            if planillas.exists():
                # Delete all values for this piece across relevant planillas
                # Ensure piece is treated as int for DB matching
                try:
                    pieza_int = int(str(pieza))
                    count, _ = ValorMedicion.objects.filter(planilla__in=planillas, pieza=pieza_int).delete()
                    return JsonResponse({'status': 'success', 'deleted': count})
                except ValueError:
                    return JsonResponse({'status': 'error', 'message': f'Número de pieza inválido: {pieza}'}, status=400)
            else:
                return JsonResponse({'status': 'error', 'message': f'No se encontraron planillas configuradas para Proyecto: {proy}, OP: {op}'}, status=404)
                 
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)

@csrf_exempt
@supervisor_required
def eliminar_planilla_completa_ajax(request, planilla_id):
    if request.method == 'POST':
        try:
            planilla = get_object_or_404(PlanillaMedicion, id=planilla_id)
            # Delete associated data if not handled by cascade
            # ValorMedicion explicitly linked to planilla
            ValorMedicion.objects.filter(planilla=planilla).delete()
            # Tolerancia records for this planilla
            planilla.tolerancia_set.all().delete()
            # Finally the planilla itself
            planilla.delete()
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Solo POST permitido'}, status=405)

@supervisor_required
def estadisticas_control(request, tolerancia_id):
    import math
    import statistics
    from django.shortcuts import render, get_object_or_404
    from .models import Tolerancia, ValorMedicion

    tolerancia = get_object_or_404(Tolerancia, id=tolerancia_id)
    # Get all values for this specific control in this specific structure (Planilla)
    valores_query = ValorMedicion.objects.filter(
        planilla=tolerancia.planilla, 
        control=tolerancia.control
    ).order_by('pieza')
    
    # Filter only numeric values
    data_points = []
    labels = []
    for v in valores_query:
        if v.valor_pieza is not None:
            data_points.append(float(v.valor_pieza))
            labels.append(f"P{v.pieza}")

    import statistics
    from .utils_spc import SPCAnalyzer
    
    # Pre-calculate limits
    lsl, usl = tolerancia.get_absolute_limits()
    
    # Initialize Analyzer
    analyzer = SPCAnalyzer(data_points, nominal=tolerancia.nominal, min_limit=lsl, max_limit=usl, subgroup_size=5)
    
    # Get Advanced X-R Data
    xr_data = analyzer.get_xr_data()
    nelson_violations = analyzer.check_nelson_rules()
    cp, cpk = analyzer.get_capability_indices()

    # Prepare stats for template
    def safe_round(val, digits=4):
        if val is None: return None
        try:
            import math
            if math.isinf(val) or math.isnan(val): return None
            return round(float(val), digits)
        except: return None

    # Classification Logic
    def get_capability_status(value):
        if value is None: return None
        if value < 1.0: return {'text': 'INACEPTABLE', 'class': 'badge-soft-danger'}
        elif value < 1.33: return {'text': 'BAJA CAPACIDAD', 'class': 'badge-soft-warning'}
        elif value < 1.67: return {'text': 'CAPAZ', 'class': 'badge-soft-success'}
        else: return {'text': 'EXCELENTE', 'class': 'badge-soft-excellent'}

    # Batch Status Calculation (Aproved/Rejected pieces)
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

    # Build advanced stats dictionary
    stats = {
        'n': len(data_points),
        'mean': safe_round(analyzer.mean),
        'stdev': safe_round(analyzer.std),
        'min': safe_round(min(data_points)) if data_points else None,
        'max': safe_round(max(data_points)) if data_points else None,
        'range': safe_round(max(data_points) - min(data_points)) if data_points else None,
        'lsl': safe_round(lsl),
        'usl': safe_round(usl),
        'cp': safe_round(cp, 2),
        'cpk': safe_round(cpk, 2),
        'cp_info': get_capability_status(cp),
        'cpk_info': get_capability_status(cpk),
        'nominal': safe_round(tolerancia.nominal),
        'lic': safe_round(analyzer.mean - 3 * analyzer.std) if analyzer.mean and analyzer.std else None,
        'lsc': safe_round(analyzer.mean + 3 * analyzer.std) if analyzer.mean and analyzer.std else None,
        'n_approved': n_approved,
        'n_rejected': n_rejected,
        'n_total': n_approved + n_rejected
    }

    if xr_data:
        stats.update({
            'avg_range': safe_round(xr_data['avg_range']),
            'ucl_x': safe_round(xr_data['ucl_x']),
            'lcl_x': safe_round(xr_data['lcl_x']),
            'ucl_r': safe_round(xr_data['ucl_r']),
            'lcl_r': safe_round(xr_data['lcl_r']),
            'num_subgroups': xr_data['num_subgroups'],
            'x_bars': [safe_round(x) for x in xr_data['x_bars']],
            'ranges': [safe_round(r) for r in xr_data['ranges']],
        })

    # Convert Nelson violations to template alerts
    alerts = []
    icon_map = {1: 'ri-error-warning-line', 2: 'ri-line-chart-line', 3: 'ri-funds-line', 4: 'ri-pulse-line'}
    type_map = {1: 'danger', 2: 'warning', 3: 'warning', 4: 'info'}
    
    for v in nelson_violations:
        alerts.append({
            'title': v['title'],
            'desc': v['desc'],
            'type': type_map.get(v['rule'], 'secondary'),
            'icon': icon_map.get(v['rule'], 'ri-information-line')
        })
    
    # Capacidad alert
    if cpk is not None and cpk < 1.0:
        alerts.append({
            'title': 'Capacidad Crítica',
            'desc': f'Índice CPK ({round(cpk,2)}) fuera de norma. El proceso producirá desperdicio.',
            'type': 'danger',
            'icon': 'ri-close-circle-line'
        })
    
    stats['alerts'] = alerts

    # Fetch siblings for navigation
    hermanos = Tolerancia.objects.filter(
        planilla__proyecto=tolerancia.planilla.proyecto,
        planilla__num_op=tolerancia.planilla.num_op
    ).select_related('control', 'planilla', 'planilla__elemento').order_by('planilla__elemento__nombre', 'posicion')

    import json
    context = {
        'tolerancia': tolerancia,
        'controles_hermanos': hermanos,
        'stats': stats,
        'data_points': data_points,
        'labels': labels,
        'stats_json': json.dumps(stats),
        'data_points_json': json.dumps(data_points),
        'labels_json': json.dumps(labels),
        'titulo': f'SPC - {tolerancia.control.nombre}',
        'is_xr_available': xr_data is not None
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'stats': stats,
            'data_points': data_points,
            'labels': labels,
            'control_nombre': tolerancia.control.nombre,
            'id': tolerancia.id,
            'planilla_id': tolerancia.planilla.id,
            'is_xr_available': xr_data is not None,
            'proceso_id': tolerancia.planilla.proceso.id,
            'proceso_nombre': tolerancia.planilla.proceso.nombre,
            'num_op': tolerancia.planilla.num_op,
            'proyecto': tolerancia.planilla.proyecto,
            'cliente': tolerancia.planilla.cliente.nombre
        })

    return render(request, 'mediciones/estadisticas_control.html', context)

@login_required
def panel_control_geografico(request):
    maquinas = Maquina.objects.all()
    maquina_status = []
    
    for m in maquinas:
        # Get the latest planilla for this machine that has measurements
        last_planilla = PlanillaMedicion.objects.filter(maquina=m).order_by('-id').first()
        status = 'neutral' # No data
        info = "Sin datos recientes"
        
        if last_planilla:
            # Check values in the last planilla
            valores = ValorMedicion.objects.filter(planilla=last_planilla).select_related('tolerancia', 'control')
            
            if valores.exists():
                is_nok = False
                for v in valores:
                    if v.control.pnp:
                        if v.valor_pnp == 'NOK':
                            is_nok = True
                            break
                    else:
                        if v.valor_pieza is not None and v.tolerancia:
                            min_l, max_l = v.tolerancia.get_absolute_limits()
                            if min_l is not None and max_l is not None:
                                if v.valor_pieza < min_l or v.valor_pieza > max_l:
                                    is_nok = True
                                    break
                
                status = 'failed' if is_nok else 'approved'
                info = f"OP: {last_planilla.num_op} - {last_planilla.proceso.nombre if last_planilla.proceso else ''}"
            
        maquina_status.append({
            'id': m.id,
            'nombre': m.nombre,
            'codigo': m.codigo,
            'x_pos': m.x_pos or 0,
            'y_pos': m.y_pos or 0,
            'status': status,
            'info': info
        })
    
    return render(request, 'mediciones/panel_geografico.html', {'maquina_status': maquina_status})

@csrf_exempt
@supervisor_required
def api_update_maquina_pos(request):
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            maquina_id = data.get('id')
            x = data.get('x')
            y = data.get('y')
            
            m = Maquina.objects.get(id=maquina_id)
            m.x_pos = x
            m.y_pos = y
            m.save()
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

@login_required
def modo_operario(request):
    """Vista standalone para la pantalla del operario (tablet)."""
    return render(request, 'mediciones/operario_medicion.html')

@login_required
def operario_medicion(request):
    """Vista standalone para la pantalla del operario (tablet)."""
    return render(request, 'mediciones/operario_medicion.html')

@login_required
def api_buscar_op_endpoint(request, op):
    """
    API para buscar planillas por Número de OP.
    Retorna información básica para que el operador elija o confirmar.
    """
    # Intentar búsqueda flexible (como entero y como string si fuera necesario)
    try:
        op_int = int(op)
        planillas = PlanillaMedicion.objects.filter(num_op=op_int).select_related('proceso', 'cliente')
    except (ValueError, TypeError):
        planillas = PlanillaMedicion.objects.filter(num_op=op).select_related('proceso', 'cliente')
    
    if not planillas.exists():
        # Fallback por si acaso está guardado en un formato inesperado
        planillas = PlanillaMedicion.objects.filter(num_op__icontains=str(op)).select_related('proceso', 'cliente')
        
    if not planillas.exists():
        return JsonResponse({'status': 'error', 'message': f'No se encontró la OP #{op}.'})
    
    unique_procs = {}
    
    for p in planillas:
        # Asegurarnos de tener un proceso
        proc_id = p.proceso.id if p.proceso else 0
        # Usar proyecto + proceso como clave única para evitar duplicados en la selección
        key = f"{p.proyecto}_{proc_id}"
        
        if key not in unique_procs:
            unique_procs[key] = {
                'id': p.id,
                'proyecto': p.proyecto or 'Sin Proyecto',
                'proceso_id': proc_id,
                'proceso_nombre': p.proceso.nombre if p.proceso else 'Sin Proceso',
                'op': p.num_op,
                'cliente': p.cliente.nombre if p.cliente else 'Sin Cliente'
            }
            
    results = list(unique_procs.values())
    
    return JsonResponse({
        'status': 'success', 
        'count': len(results),
        'results': results,
        'proyecto': results[0]['proyecto'] if len(results) > 0 else '',
        'proceso_id': results[0]['proceso_id'] if len(results) > 0 else ''
    })


@login_required
def api_operario_data(request):
    """
    API JSON endpoint for the operator tablet screen.
    Returns measurement data (tolerances, existing values, instruments) for a given OP/process/piece.
    """
    proy = request.GET.get('proy', '').strip()
    op = request.GET.get('op', '').strip()
    proc_id = request.GET.get('proc', '').strip()
    pieza = request.GET.get('pieza', '1').strip()
    
    try:
        pieza = int(pieza)
    except:
        pieza = 1
    
    if not proy or not op:
        return JsonResponse({'status': 'error', 'message': 'Faltan parámetros (proy, op).'})
    
    # Find planillas
    try:
        op_clean = str(op).strip()
        if op_clean.isdigit():
            planillas = PlanillaMedicion.objects.filter(proyecto=proy, num_op=int(op_clean))
            if not planillas.exists():
                planillas = PlanillaMedicion.objects.filter(proyecto=proy, num_op=op_clean)
        else:
            planillas = PlanillaMedicion.objects.filter(proyecto=proy, num_op=op_clean)
    except Exception:
        planillas = PlanillaMedicion.objects.filter(proyecto=proy, num_op=op)
    
    if proc_id and proc_id != 'None' and proc_id.isdigit():
        planillas = planillas.filter(proceso_id=proc_id)
    
    planillas = planillas.select_related('cliente', 'proceso', 'elemento')
    
    if not planillas.exists():
        return JsonResponse({'status': 'error', 'message': 'No se encontraron planillas.'})
    
    first_planilla = planillas.first()
    
    # Load tolerances across all matching planillas
    tolerancias = Tolerancia.objects.filter(
        planilla__in=planillas
    ).select_related(
        'control', 'planilla__elemento', 'planilla__proceso', 'instrumento'
    ).order_by('planilla__elemento__nombre', 'posicion')
    
    # Load existing values
    valores_existentes = ValorMedicion.objects.filter(planilla__in=planillas, pieza=pieza)
    valores_dict = {(v.planilla_id, v.control_id): v for v in valores_existentes}
    
    # Build rows
    rows = []
    for tol in tolerancias:
        val_obj = valores_dict.get((tol.planilla_id, tol.control_id))
        current_val = None
        status = 'pending'
        
        if val_obj:
            if tol.control.pnp:
                current_val = val_obj.valor_pnp
                if current_val == 'OK':
                    status = 'ok'
                elif current_val == 'NOK':
                    status = 'nok'
            else:
                current_val = val_obj.valor_pieza
                if current_val is not None:
                    try:
                        val_f = float(current_val)
                        min_limit, max_limit = tol.get_absolute_limits()
                        
                        is_ok = True
                        if min_limit is not None and val_f < min_limit:
                            is_ok = False
                        if max_limit is not None and val_f > max_limit:
                            is_ok = False
                        
                        status = 'ok' if is_ok else 'nok'
                    except:
                        status = 'pending'
        
        rows.append({
            'tolerancia_id': tol.id,
            'control_nombre': tol.control.nombre,
            'is_pnp': tol.control.pnp,
            'nominal': float(tol.nominal) if tol.nominal is not None else None,
            'tol_min': float(tol.minimo) if tol.minimo is not None else None,
            'tol_max': float(tol.maximo) if tol.maximo is not None else None,
            'valor': current_val,
            'status': status,
            'instrumento_id': tol.instrumento_id,
            'elemento_nombre': tol.planilla.elemento.nombre if tol.planilla.elemento else None,
        })
    
    # Piece navigation
    piezas_medidas = list(
        ValorMedicion.objects.filter(planilla__in=planillas)
        .values_list('pieza', flat=True).distinct().order_by('pieza')
    )
    max_p = max(piezas_medidas) if piezas_medidas else 0
    range_piezas = list(piezas_medidas)
    if (max_p + 1) not in range_piezas:
        range_piezas.append(max_p + 1)
    if pieza not in range_piezas:
        range_piezas.append(pieza)
        range_piezas.sort()
    
    # Window display (max 6 pieces visible)
    window_size = 6
    try:
        current_idx = range_piezas.index(pieza)
    except ValueError:
        current_idx = 0
    
    if len(range_piezas) <= window_size:
        piezas_mostrar = range_piezas
    else:
        start = max(0, current_idx - 2)
        end = start + window_size
        if end > len(range_piezas):
            end = len(range_piezas)
            start = max(0, end - window_size)
        piezas_mostrar = range_piezas[start:end]
    
    # Instruments list
    instrumentos = list(
        Instrumento.objects.all().values('id', 'nombre').order_by('nombre')
    )
    
    return JsonResponse({
        'status': 'success',
        'proyecto': first_planilla.proyecto or '',
        'op': first_planilla.num_op,
        'cliente': first_planilla.cliente.nombre if first_planilla.cliente else '-',
        'proceso': first_planilla.proceso.nombre if first_planilla.proceso else '-',
        'pieza_actual': pieza,
        'piezas': piezas_mostrar,
        'piezas_con_datos': piezas_medidas, # New field
        'rows': rows,
        'instrumentos': instrumentos,
    })
@login_required
def exportar_pdf(request, planilla_id):
    """Generates a Quality Certificate PDF based on the provided model."""
    planilla = get_object_or_404(PlanillaMedicion, id=planilla_id)
    
    # Save the current user as the approver for this report
    planilla.aprobador = request.user
    planilla.fecha_aprobador = datetime.date.today()
    planilla.save()
    
    # Tolerancias (ordered)
    tolerancias = Tolerancia.objects.filter(planilla=planilla).select_related('control', 'instrumento').order_by('posicion')
    
    # Values
    valores = ValorMedicion.objects.filter(planilla=planilla).select_related('tolerancia', 'control')
    
    # Build a lookup dict: (tolerancia_id, pieza) -> value
    valores_dict = {}
    piezas_set = set()
    for v in valores:
        key = (v.tolerancia_id, v.pieza)
        valores_dict[key] = v.valor_pnp if v.control.pnp else v.valor_pieza
        piezas_set.add(v.pieza)
    
    piezas_ordenadas = sorted(list(piezas_set))
    
    # Horizontal grouping: The image shows 15 columns. 
    # If there are more, we might want to split or just show all. 
    # For now, let's limit to the first 15 to match the template precisely, 
    # or better, provide all and let the template decide layout.
    
    rows = []
    for tol in tolerancias:
        # Build pieces data for this control
        p_data = []
        for p in piezas_ordenadas:
            val = valores_dict.get((tol.id, p))
            p_data.append({
                'num': p,
                'val': val if val is not None else ''
            })
            
        # Format tolerance range
        if tol.control.pnp:
            tol_str = "PASA / NO PASA"
        else:
            min_str = f"{tol.minimo:g}" if tol.minimo is not None else "-"
            max_str = f"{tol.maximo:g}" if tol.maximo is not None else "-"
            tol_str = f"{min_str} / {max_str}"

        rows.append({
            'detalle': tol.control.nombre,
            'solicitado': f"{tol.nominal:g}" if tol.nominal is not None else "-",
            'tolerancia': tol_str,
            'instrumento': tol.instrumento.codigo if tol.instrumento and tol.instrumento.codigo else (tol.instrumento.nombre if tol.instrumento else "-"),
            'piezas': p_data
        })

    # Identificar quién elaboró (usualmente el primer operario que cargó un valor)
    first_valor = ValorMedicion.objects.filter(planilla=planilla).order_by('fecha').first()
    elaborador_nombre = "-"
    if first_valor and first_valor.id_operario:
        try:
            op_user = User.objects.get(id=first_valor.id_operario)
            elaborador_nombre = op_user.get_full_name() or op_user.username
        except User.DoesNotExist:
            elaborador_nombre = f"Operario ID {first_valor.id_operario}"

    # Header info
    context = {
        'planilla': planilla,
        'rows': rows,
        'piezas_headers': piezas_ordenadas[:15], 
        'fecha_emision': timezone.now().strftime('%d/%m/%Y'),
        'num_registro': 'RQ-11', 
        'rev': '00', 
        'rev_fecha': '24/06/2022',
        'elaborador_nombre': elaborador_nombre,
        'aprobador_nombre': request.user.get_full_name() or request.user.username,
        'observaciones': planilla.observaciones or ""
    }
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Reporte_Calidad_OP_{planilla.num_op}.pdf"'
    
    template = get_template('mediciones/reporte_calidad_pdf.html')
    html = template.render(context)
    
    pisa_status = pisa.CreatePDF(html, dest=response)
    
    if pisa_status.err:
        return HttpResponse('Error al generar el reporte PDF', status=500)
        
    return response

@csrf_exempt
@login_required
def exportar_pdf_pro(request, planilla_id):
    """Generates an Advanced Quality Report with SPC charts."""
    from .utils_pdf import generate_xbar_chart, generate_r_chart, generate_capability_chart
    from .utils_spc import SPCAnalyzer
    import math

    planilla = get_object_or_404(PlanillaMedicion, id=planilla_id)
    tolerancias = Tolerancia.objects.filter(planilla=planilla).select_related('control', 'instrumento').order_by('posicion')
    
    params_spc = []
    
    for tol in tolerancias:
        if tol.control.pnp: continue
        
        # Get data
        valores_query = ValorMedicion.objects.filter(planilla=planilla, control=tol.control).order_by('pieza')
        data_points = [float(v.valor_pieza) for v in valores_query if v.valor_pieza is not None]
        labels = [f"P{v.pieza}" for v in valores_query if v.valor_pieza is not None]
        
        if not data_points: continue
        
        lsl, usl = tol.get_absolute_limits()
        analyzer = SPCAnalyzer(data_points, nominal=tol.nominal, min_limit=lsl, max_limit=usl, subgroup_size=5)
        xr_data = analyzer.get_xr_data()
        nelson_violations = analyzer.check_nelson_rules()
        cp, cpk = analyzer.get_capability_indices()
        
        # Helper for capability status
        def get_capability_status(value):
            if value is None: return None
            if value < 1.0: return {'text': 'INACEPTABLE', 'class': 'badge-soft-danger'}
            elif value < 1.33: return {'text': 'BAJA CAPACIDAD', 'class': 'badge-soft-warning'}
            elif value < 1.67: return {'text': 'CAPAZ', 'class': 'badge-soft-success'}
            else: return {'text': 'EXCELENTE', 'class': 'badge-soft-excellent'}

        # Prepare stats
        def safe_r(val):
            if val is None or math.isinf(val) or math.isnan(val): return None
            return round(val, 4)

        stats = {
            'n': len(data_points),
            'mean': safe_r(analyzer.mean),
            'stdev': safe_r(analyzer.std),
            'range': safe_r(max(data_points) - min(data_points)),
            'cp': safe_r(cp),
            'cpk': safe_r(cpk),
            'cpk_info': get_capability_status(cpk),
            'lic': safe_r(analyzer.mean - 3 * analyzer.std) if analyzer.mean and analyzer.std else None,
            'lsc': safe_r(analyzer.mean + 3 * analyzer.std) if analyzer.mean and analyzer.std else None,
        }
        
        # Convert Nelson violations to alerts
        alerts = []
        icon_map = {1: 'ri-error-warning-line', 2: 'ri-line-chart-line', 3: 'ri-funds-line', 4: 'ri-pulse-line'}
        type_map = {1: 'danger', 2: 'warning', 3: 'warning', 4: 'info'}
        for v in nelson_violations:
            alerts.append({'title': v['title'], 'desc': v['desc'], 'type': type_map.get(v['rule'], 'secondary')})
        
        if cpk is not None and cpk < 1.0:
            alerts.append({'title': 'Capacidad Crítica', 'desc': f'CPK ({round(cpk,2)}) fuera de norma.', 'type': 'danger'})
        
        stats['alerts'] = alerts

        # Generate unique graphs for this param
        # We need to pass labels here to ensure alignment
        charts = {
            'xbar': generate_xbar_chart(data_points, xr_data, labels),
            'range': generate_r_chart(data_points, xr_data, labels),
            'gauss': generate_capability_chart(data_points, tol.nominal, lsl, usl)
        }
        
        params_spc.append({
            'nombre': tol.control.nombre,
            'nominal': tol.nominal,
            'lsl': lsl,
            'usl': usl,
            'stats': stats,
            'charts': charts
        })

    context = {
        'planilla': planilla,
        'params_spc': params_spc,
        'fecha_emision': timezone.now().strftime('%d/%m/%Y'),
    }
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Reporte_PRO_OP_{planilla.num_op}.pdf"'
    
    template = get_template('mediciones/reporte_calidad_pro_pdf.html')
    html = template.render(context)
    
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Error al generar el reporte PRO', status=500)
    return response

@login_required
def guardar_observaciones_ajax(request):
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            planilla_id = data.get('planilla_id')
            obs = data.get('observaciones', '')
            
            planilla = PlanillaMedicion.objects.get(id=planilla_id)
            planilla.observaciones = obs
            planilla.save()
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

@login_required
def ocr_lector_planos(request):
    """
    Vista Lector OCR de Planos (PDF) - Versión Avanzada.
    Simula el procesamiento de 'Vision Artificial' detectando matrices de mediciones manuscritas.
    """
    context = {}
    if request.method == 'POST' and request.FILES.get('plano_pdf'):
        pdf_file = request.FILES['plano_pdf']
        
        # 1. Simular tiempo de procesamiento pesado (IA/Vision)
        import time
        time.sleep(3) 
        
        # 2. IA/Vision Intelligence Selection (MOCK ENGINE V2)
        # We use a session-based sticky toggle to ensure that subsequent uploads 
        # return different results if the filename doesn't explicitly help us.
        last_op = request.session.get('last_ocr_op', '46681')
        
        # Check filename first for explicit match
        file_name_lower = pdf_file.name.lower()
        if '46438' in file_name_lower or '25-080' in file_name_lower or 'aspro' in file_name_lower:
            is_op_46438 = True
        elif '46681' in file_name_lower or '25-055' in file_name_lower or 'binning' in file_name_lower:
            is_op_46438 = False
        else:
            # If no clue in filename, alternate from the last one to simulate "new file detection"
            is_op_46438 = (last_op == '46681')
            
        # Update session to remember what we just returned
        request.session['last_ocr_op'] = '46438' if is_op_46438 else '46681'
        
        if is_op_46438:
            # Data for OP 46438 (Project 25-080) - ASPRO
            header_info = {
                'proyecto': '25-080',
                'op': '46438',
                'pieza_inicio': 1,
                'pieza_fin': 20,
                'denominacion': 'PRENSA VALVULA DE 4° ETAPA',
                'articulo': '15086',
                'cliente': 'ASPRO',
                'operacion': '1° OPERACIÓN TORNO'
            }
            piezas_cols = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
            extracted_matrix = [
                {
                    'control': '1. Altura Total 31.50', 'nominal': '31.50', 'tolerancia': '+0.50/-0.0', 
                    'min': '31.50', 'max': '32.00', 'instrumento': 'CAD 37',
                    'valores': ['31.51', '31.53', '31.53', '31.54', '31.51', '31.52', '31.50', '31.55', '31.58', '31.53', '31.51', '31.52', '31.53', '31.54', '31.50', '31.51', '31.52', '31.53', '31.54', '31.50']
                },
                {
                    'control': '2. Altura ranura 14.00', 'nominal': '14.00', 'tolerancia': '± 0.25', 
                    'min': '13.75', 'max': '14.25', 'instrumento': 'CAD 37',
                    'valores': ['13.95', '13.93', '13.98', '13.99', '14.01', '14.02', '14.00', '13.98', '13.95', '13.96', '13.94', '13.97', '13.98', '13.92', '13.95', '13.99', '14.00', '14.02', '13.98', '13.95']
                },
                {
                    'control': '3. Altura 8.00', 'nominal': '8.00', 'tolerancia': '± 0.25', 
                    'min': '7.75', 'max': '8.25', 'instrumento': 'CAD 37',
                    'valores': ['7.95', '8.01', '8.00', '8.02', '8.05', '8.01', '8.00', '8.03', '8.10', '8.10', '8.02', '8.01', '8.00', '8.05', '8.01', '8.00', '8.03', '8.01', '8.00', '8.05']
                },
                {
                    'control': '4. Ra (3.2)', 'nominal': '3.20', 'tolerancia': 'MAX', 
                    'min': '0.00', 'max': '3.20', 'instrumento': 'CAD 37',
                    'valores': ['OK', 'OK', 'OK', 'OK', 'OK', 'OK', 'OK', 'OK', 'OK', 'OK', 'OK', 'OK', 'OK', 'OK', 'OK', 'OK', 'OK', 'OK', 'OK', 'OK']
                },
                {
                    'control': '5. Exterior Ø 45.90', 'nominal': '45.90', 'tolerancia': '± 0.10', 
                    'min': '45.80', 'max': '46.00', 'instrumento': 'MIC 10',
                    'valores': ['45.92', '45.93', '45.95', '45.92', '45.92', '45.92', '45.92', '45.93', '45.91', '45.91', '45.92', '45.91', '45.92', '45.93', '45.92', '45.91', '45.91', '45.91', '45.91', '45.91']
                },
                {
                    'control': '6. Exterior Ø 46.28', 'nominal': '46.28', 'tolerancia': '-0.03', 
                    'min': '46.25', 'max': '46.28', 'instrumento': 'MIC 10',
                    'valores': ['46.27', '46.26', '46.26', '46.27', '46.27', '46.27', '46.22', '46.27', '46.28', '46.26', '46.27', '46.27', '46.28', '46.28', '46.27', '46.26', '46.26', '46.26', '46.26', '46.26']
                },
                {
                    'control': '7. Interior Ø 34.35', 'nominal': '34.35', 'tolerancia': '± 0.15', 
                    'min': '34.20', 'max': '34.50', 'instrumento': 'CAD 37',
                    'valores': ['34.30', '34.32', '34.31', '34.31', '34.35', '34.30', '34.32', '34.35', '34.31', '34.28', '34.30', '34.32', '34.31', '34.35', '34.30', '34.32', '34.35', '34.31', '34.30', '34.30']
                },
                {
                    'control': '8. Ancho ranura 3.70', 'nominal': '3.70', 'tolerancia': '+- 0.10', 
                    'min': '3.60', 'max': '3.80', 'instrumento': 'CAD 32',
                    'valores': ['3.69', '3.70', '3.70', '3.68', '3.69', '3.69', '3.69', '3.68', '3.67', '3.67', '3.68', '3.62', '3.63', '3.68', '3.63', '3.67', '3.69', '3.70', '3.66', '3.64']
                },
                {
                    'control': '9. Ranura Ø 42.18', 'nominal': '42.18', 'tolerancia': '± 0.05', 
                    'min': '42.13', 'max': '42.23', 'instrumento': 'MIC 10',
                    'valores': ['42.08', '42.14', '42.12', '42.13', '42.10', '42.11', '42.10', '42.10', '42.12', '42.09', '42.11', '42.10', '42.12', '42.13', '42.12', '42.11', '42.10', '42.12', '42.10', '42.09']
                }
            ]
        else:
            # Default Data for OP 46681 (Project 25-055) - BINNING
            header_info = {
                'proyecto': '25-055', # Specifically from "N° PROYECTO"
                'op': '46681',
                'pieza_inicio': 1,
                'pieza_fin': 22,
                'denominacion': 'BOLSILLO 1" KGD',      # -> Mapped to Proceso in DB
                'articulo': '109432',                 # -> Mapped to Articulo in DB
                'cliente': 'BINNING OILTOOLS S.A',    # -> Mapped to Cliente in DB
                'operacion': 'AGUJEREADO Y FRESADO EN 4TO EJE' # -> Mapped to Elemento in DB
            }
            piezas_cols = [
                1, 3, 2, 4, 5, 6, 27, 26, 24, 14,             # Bloque 1
                13, 11, 12, 15, 17, 16, 8, 25, 10, 9, 7, 23, 22 # Bloque 2
            ]
            extracted_matrix = [
                {
                    'control': '1. Ancho Fresado', 
                    'nominal': '35.70', 'tolerancia': '± 0.20', 
                    'min': '35.50', 'max': '35.90', 'instrumento': 'CAD 45',
                    'valores': [
                        '35.68', '35.63', '35.67', '35.68', '35.64', '35.77', '35.70', '35.72', '35.72', '35.70', # B1
                        '35.65', '35.65', '35.60', '35.66', '35.68', '35.71', '35.74', '35.69', '35.70', '35.72', '35.69', '35.70', '35.72' # B2
                    ]
                },
                {
                    'control': '2. Largo Fresado', 
                    'nominal': '66.70', 'tolerancia': '± 0.30', 
                    'min': '66.40', 'max': '67.00', 'instrumento': 'CPR 4',
                    'valores': [
                        '66.68', '66.70', '66.68', '66.69', '66.98', '67.00', '66.96', '66.98', '66.95', '66.95',
                        '66.75', '66.70', '66.89', '66.77', '66.81', '66.83', '66.80', '66.81', '66.78', '66.79', '66.81', '66.86', '66.84'
                    ]
                },
                {
                    'control': '3. Alt. Inc. Lado 1', 
                    'nominal': '39.00', 'tolerancia': '± 0.20', 
                    'min': '38.80', 'max': '39.20', 'instrumento': 'CPR 4',
                    'valores': [
                        '39.20', '39.12', '39.10', '39.10', '39.12', '39.08', '39.02', '39.03', '39.01', '39.02',
                        '38.90', '39.00', '39.00', '38.85', '38.86', '38.94', '39.00', '38.97', '38.95', '38.98', '38.93', '39.03', '38.89'
                    ]
                },
                {
                    'control': '4. Alt. Inc. Lado 2', 
                    'nominal': '36.00', 'tolerancia': '± 0.20', 
                    'min': '35.80', 'max': '36.20', 'instrumento': 'CPR 4',
                    'valores': [
                        '36.10', '36.05', '36.03', '36.02', '36.04', '36.04', '36.02', '36.03', '36.03', '36.04',
                        '35.94', '35.90', '36.06', '36.12', '36.06', '36.10', '36.08', '36.05', '36.10', '36.05', '36.04', '36.10'
                    ]
                },
                {
                    'control': '5. Distancia Ø10', 
                    'nominal': '162.00', 'tolerancia': '± 0.50', 
                    'min': '161.50', 'max': '162.50', 'instrumento': 'CAD 45',
                    'valores': [
                        '161.96', '161.94', '161.97', '161.95', '161.99', '161.97', '162.00', '162.01', '162.00', '162.02',
                        '162.00', '162.00', '162.00', '162.00', '162.00', '162.00', '162.00', '162.00', '162.00', '162.00', '162.00', '162.00', '162.00'
                    ]
                },
                 {
                    'control': '6. E/ Centro Ø10', 
                    'nominal': '17.50', 'tolerancia': '± 0.10', 
                    'min': '17.40', 'max': '17.60', 'instrumento': 'CAD 45',
                    'valores': [
                        '17.50', '17.50', '17.50', '17.50', '17.50', '17.50', '17.50', '17.48', '17.49', '17.48',
                        '17.50', '17.50', '17.50', '17.50', '17.50', '17.50', '17.50', '17.50', '17.50', '17.50', '17.50', '17.50', '17.50'
                    ]
                },
                 {
                    'control': '7. Altura al plano', 
                    'nominal': '16.50', 'tolerancia': '± 0.10', 
                    'min': '16.40', 'max': '16.60', 'instrumento': 'CAD 45',
                    'valores': [
                        '16.50', '16.50', '16.50', '16.50', '16.50', '16.50', '16.50', '16.53', '16.50', '16.51',
                        '16.50', '16.51', '16.52', '16.50', '16.51', '16.50', '16.52', '16.54', '16.50', '16.53', '16.50', '16.50', '16.52'
                    ]
                },
                 {
                    'control': '8. Ø Agujero', 
                    'nominal': '10.00', 'tolerancia': '± 0.10', 
                    'min': '9.90', 'max': '10.10', 'instrumento': 'CAD 45',
                    'valores': [
                        '10.10', '10.12', '10.11', '10.13', '10.11', '10.10', '10.08', '10.07', '10.08', '10.06',
                        '10.05', '10.05', '10.02', '10.02', '10.01', '10.01', '10.02', '10.02', '10.06', '10.05', '10.04', '10.03', '10.02'
                    ]
                }
            ]
        
        # 3. Auto-Discovery Intelligence (Matching with DB)
        auto_matched = {
            'proceso_id': '',
            'articulo_id': '',
            'elemento_id': '',
            'cliente_id': ''
        }
        
        def fuzzy_match(model, text):
            if not text: return None
            # Tries exact first
            match = model.objects.filter(nombre__iexact=text).first()
            if match: return match
            
            # Tries normalization (uppercase, no spaces, standardizing 'TO' as '°')
            def normalize(s):
                return s.upper().replace(' ', '').replace('TO', '°').strip()
            
            clean_target = normalize(text)
            for obj in model.objects.all():
                if normalize(obj.nombre) == clean_target:
                    return obj
            return None

        def get_or_create_fuzzy(model, text):
            if not text: return None
            # Try matching existing first
            match = fuzzy_match(model, text)
            if match: return match
            # Not found? Create it automatically as requested
            return model.objects.create(nombre=text)

        # 1. Process / Denominación
        pro_obj = get_or_create_fuzzy(Proceso, header_info.get('denominacion'))
        if pro_obj: auto_matched['proceso_id'] = pro_obj.id
        
        # 2. Artículo
        art_obj = get_or_create_fuzzy(Articulo, header_info.get('articulo'))
        if art_obj: auto_matched['articulo_id'] = art_obj.id
        
        # 3. Elemento / Operación
        ele_obj = get_or_create_fuzzy(Elemento, header_info.get('operacion'))
        if ele_obj: auto_matched['elemento_id'] = ele_obj.id
        
        # 4. Cliente
        cli_obj = get_or_create_fuzzy(Cliente, header_info.get('cliente'))
        if cli_obj: auto_matched['cliente_id'] = cli_obj.id

        # Procesar validaciones en el backend (evitar lógica compleja en template)
        valid_matrix = []
        for row in extracted_matrix:
            try:
                min_val = float(row['min'])
                max_val = float(row['max'])
                processed_vals = []
                
                for v in row['valores']:
                    v_clean = str(v).strip().upper()
                    if v_clean in ['OK', 'PASA', 'PASS']:
                        processed_vals.append({'val': v, 'ok': True})
                    else:
                        try:
                            val_float = float(v.replace(',', '.'))
                            is_ok = min_val <= val_float <= max_val
                            processed_vals.append({'val': v, 'ok': is_ok})
                        except (ValueError, AttributeError):
                            processed_vals.append({'val': v, 'ok': False}) # Error parsing or NOK number
                
                # Crear nueva fila con valores procesados
                new_row = row.copy()
                new_row['valores'] = processed_vals
                valid_matrix.append(new_row)
            except ValueError:
                valid_matrix.append(row) # Fallback if limits are invalid

        import json
        context = {
            'success': True,
            'filename': pdf_file.name,
            'header': header_info,
            'auto_matched': auto_matched,
            'piezas': piezas_cols, # Using the explicit list of piece numbers
            'matrix': valid_matrix,
            # Serialized versions for JS
            'header_json': json.dumps(header_info),
            'piezas_json': json.dumps(piezas_cols),
            'matrix_json': json.dumps(valid_matrix),
            # Master data for selectors (sorted)
            'procesos': Proceso.objects.all().order_by('nombre'),
            'articulos': Articulo.objects.all().order_by('nombre'),
            'elementos': Elemento.objects.all().order_by('nombre'),
            'clientes': Cliente.objects.all().order_by('nombre'),
        }
        
    return render(request, 'mediciones/ocr_lector.html', context)

from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import json

@csrf_exempt
def importar_datos_ocr(request):
    """
    API Endpoint para recibir los datos del OCR y persistirlos en la base de datos.
    Crea/Busca: Planilla, Controles, Tolerancias, Valores.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            header = data.get('header')
            matrix = data.get('matrix')
            piezas_cols = data.get('piezas')

            print(f"\n[OCR IMPORT DEBUG] Starting import...")
            print(f"[OCR IMPORT DEBUG] Header: {header}")
            print(f"[OCR IMPORT DEBUG] Piezas: {piezas_cols}")
            print(f"[OCR IMPORT DEBUG] Matrix rows: {len(matrix) if matrix else 0}")

            if not header or not matrix:
                return JsonResponse({'status': 'error', 'message': 'Datos incompletos'}, status=400)

            # 1. Gestionar Planilla (Buscar o Crear)
            proyecto_nombre = header.get('proyecto', 'OCR Import')
            # Extract only digits from OP string if needed, assuming valid int
            op_str = str(header.get('op', '0'))
            op_numero = int(''.join(filter(str.isdigit, op_str)) or 0)
            
            print(f"[OCR IMPORT DEBUG] OP: {op_numero}, Proyecto: {proyecto_nombre}")
            
            # Additional IDs from UI selectors
            proceso_id = data.get('proceso_id')
            articulo_id = data.get('articulo_id')
            elemento_id = data.get('elemento_id')
            cliente_id = data.get('cliente_id')
            
            # Ensure we search/create by both OP and Project to be more specific
            # OPs might be repeated across different projects in some systems
            planilla, created = PlanillaMedicion.objects.get_or_create(
                num_op=op_numero,
                proyecto=proyecto_nombre,
                defaults={
                    'fecha_elaborador': timezone.now().date(),
                    'observaciones': 'Importado automáticamente via OCR',
                }
            )

            # If the planilla already existed, the user wants to refresh it from the PDF
            # So we clear existing structure (Tolerances and associated Values) to avoid duplicates
            if not created:
                planilla.tolerancia_set.all().delete()
                # Values are usually cascaded from tolerances, but also from planilla.
                # To be absolutely sure we don't have stray data for this OP:
                # (Optional: planilla.valores.all().delete() if needed, but Tolerancia.delete() should handle it)
                ValorMedicion.objects.filter(planilla=planilla).delete()
            
            # Helper to safely set FK IDs from strings/nulls
            def set_fk_id(obj, field_name, value):
                if value and str(value).isdigit():
                    setattr(obj, field_name, int(value))
                elif not value or value == 'None' or value == '':
                    # Optional: Could set to None if we want to clear it, 
                    # but for now we only set if we have a real ID
                    pass

            # Always update or set during creation
            set_fk_id(planilla, 'proceso_id', proceso_id)
            set_fk_id(planilla, 'articulo_id', articulo_id)
            set_fk_id(planilla, 'elemento_id', elemento_id)
            set_fk_id(planilla, 'cliente_id', cliente_id)
            planilla.save()

            # 2. Iterar sobre la matriz
            for i, row in enumerate(matrix):
                raw_control = row.get('control', '').strip()
                if not raw_control: continue
                
                # Clean control name: Remove leading numbers like "1. ", "2) ", etc.
                control_nombre = re.sub(r'^\d+[\.\)\-\s]+', '', raw_control).strip()
                # Remove common OCR trash at the end
                control_nombre = control_nombre.replace(']', '').replace('[', '').replace('|', '').strip()

                # A. Buscar o Crear Control
                control = Control.objects.filter(nombre__iexact=control_nombre).first()
                if not control:
                    control = Control.objects.create(nombre=control_nombre)

                # B. Detect if it should be a PnP control
                valores = row.get('valores', [])
                has_pnp_values = False
                for v_item in valores:
                    v_raw = v_item.get('val', v_item) if isinstance(v_item, dict) else v_item
                    if str(v_raw).strip().upper() in ['OK', 'PASA', 'PASS', 'NOK', 'FALLA', 'FAIL']:
                        has_pnp_values = True
                        break
                
                if has_pnp_values and not control.pnp:
                    control.pnp = True
                    control.save()

                # C. Gestionar Tolerancia
                try:
                    nominal_val = float(str(row.get('nominal', 0)).replace(',', '.'))
                    tol_str = str(row.get('tolerancia', '')).replace('±', '').replace('+', '').replace('-', '').strip()
                    tol_val = float(tol_str.replace(',', '.')) if tol_str and tol_str.replace('.','').replace(',','').isdigit() else 0.0
                except (ValueError, TypeError):
                    nominal_val, tol_val = 0.0, 0.0

                # D. Gestionar Instrumento
                instrumento_nombre = row.get('instrumento', '').strip()
                instrumento_obj = None
                if instrumento_nombre:
                    instrumento_obj = Instrumento.objects.filter(codigo__iexact=instrumento_nombre).first()
                    if not instrumento_obj:
                         instrumento_obj = Instrumento.objects.filter(nombre__iexact=instrumento_nombre).first()
                    if not instrumento_obj:
                        instrumento_obj = Instrumento.objects.create(nombre=instrumento_nombre, codigo=instrumento_nombre, tipo='OTRO')

                # E. Create/Update Tolerance record
                tolerancia, _ = Tolerancia.objects.update_or_create(
                    planilla=planilla,
                    control=control,
                    defaults={
                        'nominal': nominal_val,
                        'minimo': -tol_val,
                        'maximo': tol_val,
                        'posicion': i + 1,
                        'instrumento': instrumento_obj
                    }
                )

                # F. Guardar Valores
                limit = min(len(valores), len(piezas_cols))
                print(f"[OCR IMPORT DEBUG] Control '{control_nombre}': Processing {limit} values")
                
                valores_guardados = 0
                for idx in range(limit):
                    pieza_num = piezas_cols[idx]
                    v_item = valores[idx]
                    
                    # Handle both dictionary (from panel) and string (fallback)
                    val_raw = v_item.get('val') if isinstance(v_item, dict) else v_item
                    if val_raw is None: 
                        print(f"[OCR IMPORT DEBUG]   Pieza {pieza_num}: val_raw is None, skipping")
                        continue

                    try:
                        val_float = None
                        val_pnp = None
                        
                        # Normalize and clean noisy characters
                        val_upper = str(val_raw).strip().upper()
                        val_clean = val_upper.replace(']', '').replace('[', '').replace('|', '')
                        
                        if val_clean in ['OK', 'PASA', 'PASS']:
                            val_pnp = 'OK'
                            print(f"[OCR IMPORT DEBUG]   Pieza {pieza_num}: PNP=OK")
                        elif val_clean in ['NOK', 'FALLA', 'FAIL']:
                            val_pnp = 'NOK'
                            print(f"[OCR IMPORT DEBUG]   Pieza {pieza_num}: PNP=NOK")
                        else:
                            try:
                                # Extract only numbers, dots, and commas
                                val_numeric_str = re.sub(r'[^\d\.\,]', '', str(val_raw)).replace(',', '.')
                                if val_numeric_str:
                                    val_float = float(val_numeric_str)
                                    print(f"[OCR IMPORT DEBUG]   Pieza {pieza_num}: Float={val_float} (from '{val_raw}')")
                                    
                                    # Calculate status for the dashboard
                                    min_l, max_l = tolerancia.get_absolute_limits()
                                    if min_l is not None and max_l is not None:
                                        if min_l <= val_float <= max_l:
                                            val_pnp = 'OK'
                                        else:
                                            val_pnp = 'NOK'
                                    else:
                                        val_pnp = 'OK'
                                else:
                                    print(f"[OCR IMPORT DEBUG]   Pieza {pieza_num}: Empty after cleaning '{val_raw}'")
                                    continue
                            except (ValueError, TypeError) as e:
                                print(f"[OCR IMPORT DEBUG]   Pieza {pieza_num}: Parse error for '{val_raw}': {e}")
                                continue

                        # Update or create the measurement value
                        if val_pnp is not None or val_float is not None:
                            ValorMedicion.objects.update_or_create(
                                planilla=planilla,
                                control=control,
                                pieza=pieza_num,
                                defaults={
                                    'tolerancia': tolerancia,
                                    'valor_pieza': val_float,
                                    'valor_pnp': val_pnp,
                                    'op': str(planilla.num_op)
                                }
                            )
                            valores_guardados += 1
                    except Exception as e:
                        print(f"[OCR IMPORT DEBUG]   Pieza {pieza_num}: Exception {e}")
                        continue
                
                print(f"[OCR IMPORT DEBUG] Control '{control_nombre}': Saved {valores_guardados}/{limit} values")

            return JsonResponse({
                'status': 'success', 
                'message': f'Datos importados correctamente a la OP {op_numero}',
                'op': op_numero,
                'proy': planilla.proyecto,
                'proc_id': planilla.proceso_id
            })

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
