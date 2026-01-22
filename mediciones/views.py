from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.http import JsonResponse
from .models import PlanillaMedicion, Cliente, Articulo, Proceso, Elemento, Control, Tolerancia, ValorMedicion
from .forms import PlanillaForm, ClienteForm, ArticuloForm, ProcesoForm, ElementoForm, ControlForm
from django.views.decorators.csrf import csrf_exempt

def index(request):
    planillas = PlanillaMedicion.objects.all().order_by('-id')[:15]
    return render(request, 'mediciones/index.html', {'planillas': planillas})

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
            else:
                return JsonResponse({'status': 'error', 'message': 'Modelo inválido'}, status=400)
            
            return JsonResponse({'status': 'success', 'id': obj.id, 'nombre': obj.nombre})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

def api_delete_tolerancia(request, tolerancia_id):
    if request.method == 'POST':
        try:
            tol = Tolerancia.objects.get(id=tolerancia_id)
            tol.delete()
            return JsonResponse({'status': 'success'})
        except Tolerancia.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)

from django.core.paginator import Paginator

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

def eliminar_proceso(request, pk):
    proceso = get_object_or_404(Proceso, pk=pk)
    if request.method == 'POST':
        proceso.delete()
        messages.success(request, 'Proceso eliminado.')
    return redirect('lista_procesos')

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

def eliminar_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        cliente.delete()
        messages.success(request, 'Cliente eliminado.')
    return redirect('lista_clientes')

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

def eliminar_control(request, pk):
    control = get_object_or_404(Control, pk=pk)
    if request.method == 'POST':
        control.delete()
        messages.success(request, 'Control eliminado.')
    return redirect('lista_controles')

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
            
            # DEBUG: Print received data
            print("=" * 80)
            print("RECEIVED DATA:")
            print(f"Raw JSON: {data_json}")
            print(f"Parsed data: {data}")
            print("=" * 80)
            
            # Common Header
            cliente_id = data.get('cliente')
            proyecto = data.get('proyecto')
            articulo_id = data.get('articulo')
            num_op = data.get('num_op') or 0
            
            print(f"Cliente ID: {cliente_id} (type: {type(cliente_id)})")
            print(f"Proyecto: {proyecto}")
            print(f"Num OP: {num_op}")
            print(f"Procesos count: {len(data.get('procesos', []))}")
            
            cliente = Cliente.objects.get(id=cliente_id) if cliente_id else None
            articulo = Articulo.objects.get(id=articulo_id) if articulo_id else None
            
            print(f"Cliente object: {cliente}")
            print(f"Articulo object: {articulo}")
            
            # If editing (or just to be safe), we clean old records for this Proy/OP
            # This ensures we don't duplicate when "Saving" an edit
            deleted = PlanillaMedicion.objects.filter(proyecto=proyecto, num_op=num_op).delete()
            print(f"Deleted old records: {deleted}")

            procesos_data = data.get('procesos', [])
            
            if not procesos_data:
                # Create a placeholder record to save Header info if no processes are defined
                PlanillaMedicion.objects.create(
                    cliente=cliente,
                    proyecto=proyecto,
                    articulo=articulo,
                    proceso=None,
                    elemento=None,
                    num_op=num_op
                )
            
            planillas_creadas = []
            
            for p_data in procesos_data:
                proceso_id = p_data.get('id')
                proceso = Proceso.objects.get(id=proceso_id)
                
                # Element handling
                elemento_id = p_data.get('elemento_id')
                elemento = None
                if elemento_id:
                     elemento = Elemento.objects.get(id=elemento_id)
                else:
                    # Fallback or legacy name handling
                    elemento_nombre = p_data.get('elemento_nombre')
                    if elemento_nombre:
                        elemento, _ = Elemento.objects.get_or_create(nombre=elemento_nombre)

                planilla = PlanillaMedicion.objects.create(
                    cliente=cliente,
                    proyecto=proyecto,
                    articulo=articulo, # Kept for compatibility if Articulo is still used globally
                    proceso=proceso,
                    elemento=elemento,
                    num_op=num_op
                )
                planillas_creadas.append(planilla)
                
                controles_data = p_data.get('controles', [])
                for idx, c_data in enumerate(controles_data):
                    control_id = c_data.get('id')
                    control = Control.objects.get(id=control_id)
                    
                    def to_decimal(val):
                        if val == '' or val is None: return None
                        try:
                            if isinstance(val, str):
                                val = val.replace(',', '.')
                            return float(val)
                        except:
                            return None

                    Tolerancia.objects.create(
                        planilla=planilla,
                        control=control,
                        minimo=to_decimal(c_data.get('min')),
                        nominal=to_decimal(c_data.get('nom')),
                        maximo=to_decimal(c_data.get('max')),
                        posicion=idx + 1
                    )
            
            return JsonResponse({
                'status': 'success', 
                'message': f'Estructura guardada con éxito.',
                'redirect_url': reverse('lista_estructuras')
            })
            
        except Exception as e:
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
def nueva_medicion_op(request):
    proy_query = request.GET.get('proy', '')
    op_query = request.GET.get('op', '')
    proc_id = request.GET.get('proc', '')
    pieza_actual = request.GET.get('pieza', 1)
    
    try:
        pieza_actual = int(pieza_actual)
    except:
        pieza_actual = 1
        
    planilla = None
    rows = []
    
    # 1. Selection logic
    if proy_query and op_query:
        # Build filter dynamically
        filters = {'proyecto': proy_query, 'num_op': op_query}
        if proc_id and proc_id != 'None':
            filters['proceso_id'] = proc_id
            
        planillas = PlanillaMedicion.objects.filter(**filters).select_related('elemento', 'proceso')
        
        if planillas.exists():
            # 2. Load Controls/Tolerances from ALL planillas found
            tolerancias = Tolerancia.objects.filter(planilla__in=planillas).select_related('control', 'planilla__elemento', 'planilla__proceso').order_by('planilla__elemento__nombre', 'posicion')
            
            # 3. Handle POST (Save measurements)
            if request.method == 'POST':
                for tol in tolerancias:
                    # Determine Input Value based on Type
                    if tol.control.pnp:
                        # PNP Logic
                        val_input = request.POST.get(f'valorpnp_{tol.id}')
                        # Proceed if key exists (even if empty to allow clearing)
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
                        # Proceed if key exists (standard form submission includes all inputs)
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
                                    # If invalid number, do not update (pass) or set None?
                                    # Previously 'pass' kept old value. Let's keep 'pass' for safety against random junk,
                                    # but empty string is handled above.
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
        'titulo': 'Ingreso de Mediciones'
    }
    return render(request, 'mediciones/nueva_medicion_op.html', context)
@csrf_exempt
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
def eliminar_pieza_ajax(request):
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        
        proy = data.get('proyecto')
        op = data.get('op')
        proc_id = data.get('proceso_id')
        pieza = data.get('pieza')
        
        # Find all planillas/tolerances for this combination
        planillas = PlanillaMedicion.objects.filter(proyecto=proy, num_op=op, proceso_id=proc_id)
        
        if planillas.exists():
            # Delete all values for this piece across all relevant planillas
            ValorMedicion.objects.filter(planilla__in=planillas, pieza=pieza).delete()
            return JsonResponse({'status': 'success'})
            
        return JsonResponse({'status': 'error', 'message': 'Operación fallida'}, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)

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
    return render(request, 'mediciones/estadisticas_control.html', context)
