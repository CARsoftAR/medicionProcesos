from .models import Instrumento
from datetime import date

def alerts_context_processor(request):
    if not request.user.is_authenticated:
        return {}
    
    # Only for Quality / Admin users
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role == 'CALIDAD')):
        return {}
        
    instrumentos = Instrumento.objects.all()
    vencidos_count = len([i for i in instrumentos if i.is_calibracion_vencida()])
    alertas_count = len([i for i in instrumentos if i.is_en_alerta()])
    
    return {
        'global_vencidos_count': vencidos_count,
        'global_alertas_count': alertas_count,
        'has_global_alerts': vencidos_count > 0 or alertas_count > 0
    }
