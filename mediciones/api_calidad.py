from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from django.shortcuts import get_object_or_404

from .models import PlanillaMedicion, Tolerancia, ValorMedicion, Control, Proceso, Articulo, Elemento, Maquina, HistorialCalibracion, Instrumento
from .serializers import ToleranciaSerializer, ValorMedicionSerializer
from django.db import transaction
from django.conf import settings


class CotasPlanillaAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, op_num, format=None):
        """
        Retorna las cotas (Tolerancias y Controles) a medir para una Orden de Proceso.
        """
        planilla = get_object_or_404(PlanillaMedicion, num_op=op_num)
        tolerancias = Tolerancia.objects.filter(planilla=planilla).select_related('control').order_by('posicion')
        serializer = ToleranciaSerializer(tolerancias, many=True)
        
        # Obtener lista de piezas ya registradas (sin repetidos, ordenadas)
        valores = ValorMedicion.objects.filter(planilla=planilla).exclude(valor_pieza__isnull=True, valor_pnp__isnull=True)
        piezas = valores.values_list('pieza', flat=True).distinct().order_by('pieza')
        piezas_registradas = list(piezas)
        
        # Agrupar los valores por pieza
        mediciones_valores = {}
        for val in valores:
            p = str(val.pieza)
            if p not in mediciones_valores:
                mediciones_valores[p] = {}
            if val.tolerancia_id:
                if val.valor_pieza is not None:
                    v = val.valor_pieza
                    # Remove trailing .0 if it's an integer to preserve exactness visually
                    val_str = str(int(v)) if v.is_integer() else str(v)
                    mediciones_valores[p][val.tolerancia_id] = val_str
                else:
                    mediciones_valores[p][val.tolerancia_id] = ''
        
        return Response({
            'planilla_id': planilla.id,
            'op_num': planilla.num_op,
            'proyecto': planilla.proyecto,
            'cliente': planilla.cliente.nombre if planilla.cliente else None,
            'cotas': serializer.data,
            'piezas_registradas': piezas_registradas,
            'mediciones_valores': mediciones_valores
        }, status=status.HTTP_200_OK)

class GuardarMedicionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, format=None):
        """
        Guarda una nueva medicin enviada desde la App Mvil, 
        quedando vinculada al request.user mediante TokenAuth.
        """
        is_many = isinstance(request.data, list)
        serializer = ValorMedicionSerializer(data=request.data, context={'request': request}, many=is_many)
        if serializer.is_valid():
            serializer.save()
            return Response({'status': 'success', 'data': serializer.data}, status=status.HTTP_201_CREATED)
        return Response({'status': 'error', 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

class BorrarPiezaAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, op_num, pieza, format=None):
        planillas = PlanillaMedicion.objects.filter(num_op=op_num)
        if not planillas.exists() and str(op_num).isdigit():
            planillas = PlanillaMedicion.objects.filter(num_op=int(op_num))
            
        if not planillas.exists():
            return Response({'status': 'error', 'message': 'OP no encontrada'}, status=status.HTTP_404_NOT_FOUND)
            
        deleted, _ = ValorMedicion.objects.filter(planilla__in=planillas, pieza=pieza).delete()
        if deleted > 0:
            return Response({'status': 'success', 'deleted': deleted}, status=status.HTTP_200_OK)
        return Response({'status': 'error', 'message': 'Pieza no encontrada o ya estaba vacía'}, status=status.HTTP_200_OK)

import logging
logger = logging.getLogger(__name__)

class OperarioLoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, format=None):
        legajo = request.data.get('legajo')
        pin = request.data.get('pin')
        
        if not legajo or not pin:
            logger.warning("Login fallido: Legajo o PIN no proporcionados.")
            return Response({'error': 'Legajo y PIN son requeridos'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(username=legajo)
        except User.DoesNotExist:
            logger.warning(f"Login fallido: Legajo inexistente ({legajo}).")
            return Response({'error': 'Legajo incorrecto'}, status=status.HTTP_404_NOT_FOUND)
        except User.MultipleObjectsReturned:
            logger.error(f"Login fallido: Múltiples usuarios encontrados para el legajo {legajo}. Intentando buscar activo.")
            users = User.objects.filter(username=legajo, is_active=True)
            if users.exists():
                user = users.first()
            else:
                return Response({'error': 'Legajo duplicado o inactivo.'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(f"Error interno en login para legajo {legajo}: {str(e)}")
            return Response({'error': 'Error interno del servidor'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if not user.check_password(pin):
            logger.warning(f"Login fallido: PIN incorrecto para legajo {legajo}.")
            return Response({'error': 'PIN incorrecto'}, status=status.HTTP_401_UNAUTHORIZED)
            
        if not user.is_active:
            logger.warning(f"Login fallido: Usuario {legajo} inactivo (is_active=False).")
            return Response({'error': 'Usuario inactivo'}, status=status.HTTP_403_FORBIDDEN)

        if hasattr(user, 'operario') and not user.operario.activo:
            logger.warning(f"Login fallido: Operario {legajo} inactivo (operario.activo=False).")
            return Response({'error': 'Operario inactivo'}, status=status.HTTP_403_FORBIDDEN)
            
        token, _ = Token.objects.get_or_create(user=user)
        logger.info(f"Login exitoso para legajo {legajo}.")
        return Response({'token': token.key}, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# VISTAS DE ESCANEO OCR — /api/calidad/escanear/
# Delegan en el motor asíncrono definido en views.py
# ─────────────────────────────────────────────────────────────────────────────
import os
import uuid
import threading
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import SystemConfig


@csrf_exempt
def escanear_planilla_view(request):
    """
    POST /api/calidad/escanear/
    Recibe la foto de la planilla desde la app móvil.
    Guarda la imagen en disco, lanza el OCR en un hilo daemon y
    responde INMEDIATAMENTE con {"status": "recibido", "task_id": "..."}.
    """
    print("--- [DEBUG] PETICIÓN DE ESCANEO RECIBIDA ---")
    print("Método:", request.method)
    print("FILES:", request.FILES)
    print("POST:", request.POST)

    if request.method != 'POST':
        return JsonResponse({"error": "Método no permitido"}, status=405)

    import traceback
    try:
        try:
            from google import genai  # noqa: solo verificar disponibilidad
        except ImportError:
            return JsonResponse({
                "status": "error",
                "message": "Librería google.genai no instalada en el servidor."
            }, status=500)

        imagen = request.FILES.get('imagen') or request.FILES.get('file') or request.FILES.get('photo')
        if not imagen:
            return JsonResponse({
                "status": "error",
                "message": "No se encontró ninguna imagen. Enviá el archivo con el campo 'imagen', 'file' o 'photo'."
            }, status=400)

        gemini_config = SystemConfig.objects.filter(key="GEMINI_API_KEY").first()
        api_key = gemini_config.value if gemini_config else None
        if not api_key:
            return JsonResponse({
                "status": "error",
                "message": "API Key de Gemini no configurada en el sistema."
            }, status=500)

        # Guardar imagen en disco de forma segura
        from django.conf import settings as django_settings
        tmp_dir = os.path.join(getattr(django_settings, 'MEDIA_ROOT', '.'), 'temporales')
        os.makedirs(tmp_dir, exist_ok=True)

        task_id  = str(uuid.uuid4())
        ext      = os.path.splitext(imagen.name)[1] if imagen.name else '.jpg'
        img_path = os.path.join(tmp_dir, f"ocr_{task_id}{ext}")

        with open(img_path, 'wb') as f:
            for chunk in imagen.chunks():
                f.write(chunk)

        mime_type = imagen.content_type or 'image/jpeg'

        # Importar el motor asíncrono y el registro de tareas desde views.py
        from .views import process_ocr_background_task, _set_task_status

        _set_task_status(task_id, 'pending')

        thread = threading.Thread(
            target=process_ocr_background_task,
            args=(task_id, img_path, mime_type, api_key),
            daemon=True
        )
        thread.start()

        logger.info(f"[OCR] Tarea {task_id} iniciada desde /api/calidad/escanear/")

        return JsonResponse({
            "status": "success",
            "message": "Imagen recibida correctamente",
            "data": {},
            "task_id": task_id
        }, status=200)
    except Exception as e:
        print("❌ ERROR CRÍTICO EN EL ESCANEO:")
        traceback.print_exc()
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@csrf_exempt
def estado_escaneo_view(request, task_id):
    """
    GET /api/calidad/escanear/estado/<task_id>/
    Polling: devuelve el estado actual del procesamiento OCR.
    Posibles valores de 'status': pending | processing | done | error
    """
    from .views import _ocr_tasks, _ocr_tasks_lock

    with _ocr_tasks_lock:
        task = _ocr_tasks.get(task_id)

    if task is None:
        return JsonResponse({
            "status": "not_found",
            "message": "Tarea no encontrada. Verificá el task_id."
        }, status=404)

    response_data = {"status": task["status"], "task_id": task_id}

    if task["status"] == "done":
        response_data["result"]  = task["result"]
        response_data["message"] = "Procesamiento completado. La planilla fue guardada en el sistema."
    elif task["status"] == "error":
        response_data["error"]   = task["error"]
        response_data["message"] = "Ocurrió un error durante el procesamiento."
    elif task["status"] == "processing":
        response_data["message"] = "El motor OCR está analizando la imagen. Volvé a consultar en unos segundos."
    else:
        response_data["message"] = "La tarea está en cola, aguardando procesamiento."

    return JsonResponse(response_data)
