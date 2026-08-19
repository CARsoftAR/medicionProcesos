from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token
from . import api_calidad

urlpatterns = [
    # 1. Endpoint de Autenticación (Devuelve el Token)
    path('login/', api_calidad.OperarioLoginAPIView.as_view(), name='api_login'),
    
    # 2. Endpoint GET de Cotas (Por Nro OP)
    path('cotas/op/<int:op_num>/', api_calidad.CotasPlanillaAPIView.as_view(), name='api_cotas_op'),
    
    # 3. Endpoint POST de Medición
    path('mediciones/guardar/', api_calidad.GuardarMedicionAPIView.as_view(), name='api_guardar_medicion'),
    
    # 4. Endpoint DELETE de Pieza
    path('mediciones/op/<int:op_num>/pieza/<int:pieza>/', api_calidad.BorrarPiezaAPIView.as_view(), name='api_borrar_pieza'),
    
    # 5. Endpoint POST de Escaneo OCR (App Móvil → Planilla)
    path('escanear/', api_calidad.escanear_planilla_view, name='api_escanear_planilla'),
    
    # 6. Polling: estado del procesamiento OCR
    path('escanear/estado/<str:task_id>/', api_calidad.estado_escaneo_view, name='api_estado_escaneo'),
]
