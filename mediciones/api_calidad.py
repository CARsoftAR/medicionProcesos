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
    Procesa la imagen usando google.genai de forma sincrónica.
    """
    print("--- [DEBUG] PETICIÓN DE ESCANEO RECIBIDA ---")
    print("Método:", request.method)
    print("FILES:", request.FILES)
    print("POST:", request.POST)

    if request.method != 'POST':
        return JsonResponse({"error": "Método no permitido"}, status=405)

    import traceback
    try:
        from google import genai
        import json
        from .models import SystemConfig

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
            }, status=400)

        # --- Manejo seguro y compresión de la imagen ---
        import io
        from PIL import Image

        try:
            img = Image.open(imagen)
            # Convertir a RGB si es necesario
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            # Redimensionar conservando proporción si excede los 1920px
            img.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
            
            # Comprimir a JPEG con calidad 85 para alivianar el payload
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='JPEG', quality=85)
            img_data = img_byte_arr.getvalue()
            mime_type = 'image/jpeg'
        except Exception as img_err:
            print("❌ ERROR AL COMPRIMIR LA IMAGEN:")
            traceback.print_exc()
            return JsonResponse({
                "status": "error",
                "message": f"Error al leer o comprimir la imagen: {str(img_err)}"
            }, status=400)

        client = genai.Client(api_key=api_key)
        image_part = {"mime_type": mime_type, "data": img_data}

        prompt = """
Extrae toda la información de esta planilla de medición de calidad y devuélvela EXCLUSIVAMENTE en formato JSON válido.
El JSON debe tener la siguiente estructura exacta:
{
  "header": {
    "cliente": "Nombre del cliente",
    "proyecto": "Nombre del proyecto",
    "op": "Numero de OP (solo dígitos)",
    "articulo": "Articulo",
    "denominacion": "Denominacion o proceso",
    "operacion": "Operacion o elemento"
  },
  "piezas": ["1", "2", "3", "4", "5"],
  "matrix": [
    {
      "control": "Nombre del control o parámetro",
      "nominal": "Valor nominal numérico o '-'",
      "tolerancia": "Texto de tolerancia (ej: ±0.1, +0.2/-0.1)",
      "instrumento": "Instrumento usado",
      "valores": [
        {"val": "Valor medido para la pieza 1"},
        {"val": "Valor medido para la pieza 2"}
      ]
    }
  ]
}
Asegúrate de leer tanto el texto impreso como las anotaciones hechas a mano (valores de medición).
Si un campo no tiene valor, envíalo como "". Solo responde con el JSON puro sin bloques markdown (sin ```json ... ```).
"""
        
        # --- Llamada al SDK envuelta de forma robusta ---
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[prompt, image_part]
            )
            response_text = response.text.strip()
        except Exception as api_err:
            print("❌ ERROR CRÍTICO EN LA IA (GEMINI SDK):")
            traceback.print_exc()
            return JsonResponse({
                "status": "error", 
                "message": f"La Inteligencia Artificial no pudo procesar la imagen: {str(api_err)}"
            }, status=400)

        # Limpiar posible markdown
        if response_text.startswith("```json"):
            response_text = response_text.replace("```json", "", 1)
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        data = json.loads(response_text.strip())

        return JsonResponse({
            "status": "success",
            "message": "Planilla procesada correctamente",
            "data": data
        }, status=200)

    except Exception as e:
        print("❌ ERROR NO CONTROLADO EN EL ESCANEO:")
        traceback.print_exc()
        return JsonResponse({"status": "error", "message": f"Fallo general del servidor: {str(e)}"}, status=400)


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
