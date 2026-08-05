import re

# Update views.py
with open('mediciones/views.py', 'r', encoding='utf-8') as f:
    views_code = f.read()

# Replace the JsonResponse in importar_datos_ocr
old_response = "return JsonResponse({'status': 'success', 'message': f'Datos importados correctamente a la OP {op_numero}', 'op': op_numero, 'proy': planilla.proyecto, 'proc_id': planilla.proceso_id})"
new_response = "return JsonResponse({'status': 'success', 'message': f'Datos importados correctamente a la OP {op_numero}', 'op': op_numero, 'proy': planilla.proyecto, 'proc_id': planilla.proceso_id, 'planilla_id': planilla.id})"

views_code = views_code.replace(old_response, new_response)

with open('mediciones/views.py', 'w', encoding='utf-8') as f:
    f.write(views_code)

# Update ocr_lector.html
with open('mediciones/templates/mediciones/ocr_lector.html', 'r', encoding='utf-8') as f:
    html = f.read()

old_redirect1 = 'window.location.href = `/mediciones/nueva/?op=${data.op}&proy=${encodeURIComponent(data.proy)}&proc=${data.proc_id}`;'
new_redirect1 = 'window.location.href = `/mediciones/${data.planilla_id}/ingresar/`;'

html = html.replace(old_redirect1, new_redirect1)

with open('mediciones/templates/mediciones/ocr_lector.html', 'w', encoding='utf-8') as f:
    f.write(html)

print('Updated redirect to point directly to the grid.')
