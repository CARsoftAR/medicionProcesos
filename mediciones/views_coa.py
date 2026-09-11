from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
def generar_certificado_ocr_pdf(request):
    if request.method == 'POST':
        try:
            from xhtml2pdf import pisa
            import io
            
            data = json.loads(request.body)
            header = data.get('header', {})
            piezas = data.get('piezas', [])
            matrix = data.get('matrix', [])
            
            context = {
                'header': header,
                'piezas': piezas,
                'matrix': matrix,
            }
            
            html = render_to_string('mediciones/certificado_coa.html', context)
            
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="CoA_OP_{header.get("op", "0")}.pdf"'
            
            pisa_status = pisa.CreatePDF(
                html, dest=response
            )
            
            if pisa_status.err:
                return JsonResponse({'status': 'error', 'message': 'We had some errors <pre>' + html + '</pre>'})
            return response
            
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
