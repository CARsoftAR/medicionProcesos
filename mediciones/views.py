from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.urls import reverse
from django.contrib import messages
from django.http import JsonResponse
from .models import PlanillaMedicion, Cliente, Articulo, Proceso, Elemento, Control, Tolerancia, ValorMedicion, Maquina, Instrumento, Profile
from .forms import PlanillaForm, ClienteForm, ArticuloForm, ProcesoForm, ElementoForm, ControlForm, UserForm
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.template.loader import get_template
from xhtml2pdf import pisa
from django.http import HttpResponse
from django.utils import timezone
import datetime

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
    planillas = PlanillaMedicion.objects.all().order_by('-id')[:15]
    return render(request, 'mediciones/index.html', {'planillas': planillas})

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
            
        planillas = planillas.select_related('elemento', 'proceso', 'cliente')

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
            
            for tol in tolerancias:
                val_obj = valores_dict.get((tol.planilla_id, tol.control_id))
                current_val = None
                status = 'PENDIENTE'
                
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
                    'status': status
                })

            # Use the first planilla for header info (Project, OP, Proceso)
            planilla = planillas.first()

        # 5. Piece Navigation Info
        piezas_medidas = ValorMedicion.objects.filter(planilla=planilla).values_list('pieza', flat=True).distinct().order_by('pieza')
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
            
            val_obj, created = ValorMedicion.objects.update_or_create(
                planilla=tol.planilla,
                control=tol.control,
                pieza=pieza,
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
                val_obj.valor_pnp = None
                if valor and valor.strip():
                    try:
                        clean_valor = valor.replace(',', '.')
                        val_obj.valor_pieza = float(clean_valor)
                        logger.info(f"AJAX Save - Converted '{valor}' -> {val_obj.valor_pieza}")
                    except Exception as conv_err:
                        logger.error(f"AJAX Save - Conversion failed: {conv_err}")
                        val_obj.valor_pieza = None
                else:
                    val_obj.valor_pieza = None
            
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
                count, _ = ValorMedicion.objects.filter(planilla__in=planillas, pieza=pieza).delete()
                return JsonResponse({'status': 'success', 'deleted': count})
            else:
                 # If no planillas found, maybe there was nothing to delete, so success?
                 # Or actually valid request but no config found.
                 # Let's return success to allow UI to proceed if it was just empty.
                 return JsonResponse({'status': 'success', 'message': 'No matching planillas found, nothing to delete.'})
                 
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)

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

    # Calculations
    stats = {}
    if len(data_points) > 1:
        mean = statistics.mean(data_points)
        try:
            stdev = statistics.stdev(data_points)
        except:
            stdev = 0
            
        lsl, usl = tolerancia.get_absolute_limits()
        nominal = float(tolerancia.nominal) if tolerancia.nominal is not None else mean
        
        # Batch Status Calculation (Corrected)
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
                        is_ok = True
                        if lsl is not None and vf < lsl: is_ok = False
                        if usl is not None and vf > usl: is_ok = False
                        
                        if not is_ok: n_rejected += 1
                        else: n_approved += 1
                    except: pass

        # Cp and Cpk
        cp = None
        cpk = None
        
        if stdev > 0:
            # Cp requires both limits
            if usl is not None and lsl is not None:
                cp = (usl - lsl) / (6 * stdev)
            
            # Cpk can be calculated with one or both
            cpk_u = (usl - mean) / (3 * stdev) if usl is not None else float('inf')
            cpk_l = (mean - lsl) / (3 * stdev) if lsl is not None else float('inf')
            cpk = min(cpk_u, cpk_l)
            if cpk == float('inf'): cpk = None
        
        # Ranges for R chart
        ranges = []
        for i in range(1, len(data_points)):
            ranges.append(abs(data_points[i] - data_points[i-1]))
        r_mean = statistics.mean(ranges) if ranges else 0
        
        # Control Limits (R-Chart Moving Range n=2)
        r_lsc = r_mean * 3.267
        r_lic = 0 # D3 is 0 for n=2
        
        # Control Limits (X-bar chart) - Using individuals logic
        lic = mean - (3 * stdev)
        lsc = mean + (3 * stdev)
        
        def safe_round(val, digits=4):
            if val is None: return None
            try:
                import math
                if math.isinf(val) or math.isnan(val): return None
                return round(float(val), digits)
            except:
                return None

        stats = {
            'n': len(data_points),
            'mean': safe_round(mean),
            'stdev': safe_round(stdev),
            'max': safe_round(max(data_points)),
            'min': safe_round(min(data_points)),
            'range': safe_round(max(data_points) - min(data_points)),
            'lsl': safe_round(lsl),
            'usl': safe_round(usl),
            'cp': safe_round(cp, 2),
            'cpk': safe_round(cpk, 2),
            'lic': safe_round(lic),
            'lsc': safe_round(lsc),
            'r_mean': safe_round(r_mean),
            'r_lsc': safe_round(r_lsc),
            'r_lic': safe_round(r_lic),
            'nominal': safe_round(nominal),
            'n_approved': n_approved,
            'n_rejected': n_rejected,
            'n_total': n_approved + n_rejected
        }

        # Classification Logic
        def get_capability_status(value):
            if value is None:
                return None
            if value < 1.0:
                return {'text': 'INACEPTABLE', 'class': 'badge-soft-danger'}
            elif value < 1.33:
                return {'text': 'ACEPTABLE CON INSPECCIÓN RIGUROSA', 'class': 'badge-soft-warning'}
            elif value < 2.0:
                return {'text': 'ACEPTABLE', 'class': 'badge-soft-success'}
            else:
                return {'text': 'EXCELENTE', 'class': 'badge-soft-excellent'} # Or a distinctive green

        stats['cp_info'] = get_capability_status(cp)
        stats['cpk_info'] = get_capability_status(cpk)

        # --- Alertas Inteligentes (Reglas de Control SPC) ---
        alerts = []
        if len(data_points) >= 2:
            # Regla 1: Fuera de límites de control (±3σ)
            out_points = []
            for i, val in enumerate(data_points):
                if (lic is not None and val < lic) or (lsc is not None and val > lsc):
                    out_points.append(f"P{i+1}")
            
            if out_points:
                alerts.append({
                    'title': 'Inestabilidad: Fuera de Control',
                    'desc': f'Los puntos {", ".join(out_points)} están fuera de los límites estadísticos (±3σ). El proceso no es predecible.',
                    'type': 'danger',
                    'icon': 'ri-alarm-warning-line'
                })

            # Regla 2: Rachas (7 puntos seguidos de una lado del promedio)
            count_above = 0
            count_below = 0
            for val in data_points:
                if val > mean: 
                    count_above += 1
                    count_below = 0
                elif val < mean:
                    count_below += 1
                    count_above = 0
                else:
                    count_above = 0
                    count_below = 0
                
                if count_above >= 7 or count_below >= 7:
                    side = "ENCIMA" if count_above >= 7 else "DEBAJO"
                    alerts.append({
                        'title': 'Racha Detectada',
                        'desc': f'7 o más puntos consecutivos se encuentran por {side} del promedio. Indica un posible desplazamiento del proceso.',
                        'type': 'warning',
                        'icon': 'ri-line-chart-line'
                    })
                    break

            # Regla 3: Tendencias (6 puntos seguidos subiendo o bajando)
            subiendo = 1
            bajando = 1
            for i in range(1, len(data_points)):
                if data_points[i] > data_points[i-1]:
                    subiendo += 1
                    bajando = 1
                elif data_points[i] < data_points[i-1]:
                    bajando += 1
                    subiendo = 1
                else:
                    subiendo = 1
                    bajando = 1
                
                if subiendo >= 7 or bajando >= 7:
                    trend = "ASCENDENTE" if subiendo >= 7 else "DESCENDENTE"
                    alerts.append({
                        'title': f'Tendencia {trend.capitalize()}',
                        'desc': f'Se detectaron 7 puntos consecutivos en dirección {trend}. Posible desgaste de herramienta o desajuste progresivo.',
                        'type': 'warning',
                        'icon': 'ri-funds-line'
                    })
                    break

            # Variabilidad (Zig-Zag o excesiva)
            if len(data_points) >= 14:
                zigzag = 0
                for i in range(1, len(data_points)-1):
                    if (data_points[i] > data_points[i-1] and data_points[i] > data_points[i+1]) or \
                       (data_points[i] < data_points[i-1] and data_points[i] < data_points[i+1]):
                        zigzag += 1
                    else:
                        zigzag = 0
                    
                    if zigzag >= 14:
                        alerts.append({
                            'title': 'Variabilidad Inestable',
                            'desc': 'Oscilaciones continuas detectadas (14 puntos). El proceso alterna demasiado, revisar método de medición o fijación.',
                            'type': 'info',
                            'icon': 'ri-pulse-line'
                        })
                        break
            
            # Regla de Capacidad: Proceso No Capaz (CPK < 1.0)
            if cpk is not None and cpk < 1.0:
                alerts.append({
                    'title': 'Crítico: Capacidad Insuficiente',
                    'desc': f'El índice CPK ({round(cpk, 2)}) es inaceptable. La variabilidad de la máquina supera las tolerancias permitidas.',
                    'type': 'danger',
                    'icon': 'ri-error-warning-fill'
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
        'titulo': f'SPC - {tolerancia.control.nombre}'
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'stats': stats,
            'data_points': data_points,
            'labels': labels,
            'control_nombre': tolerancia.control.nombre,
            'id': tolerancia.id,
            'proceso_id': tolerancia.planilla.proceso.id,
            'proceso_nombre': tolerancia.planilla.proceso.nombre,
            'num_op': tolerancia.planilla.num_op,
            'proyecto': tolerancia.planilla.proyecto,
            'cliente': tolerancia.planilla.cliente.nombre,
            'is_pnp': tolerancia.control.pnp
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
