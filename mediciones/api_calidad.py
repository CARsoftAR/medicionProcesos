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

import os
import google.generativeai as genai
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

# --- CLAVE FIJA TEMPORAL PARA PROBAR ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

class EscanearPlanillaView(APIView):
    """
    POST /api/calidad/escanear/
    Recibe la foto de la planilla, la procesa con Gemini para extraer
    los datos OCR, y devuelve el mismo JSON que CotasPlanillaAPIView
    para que Flutter pueda renderizarlo directamente.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        import io, json, traceback
        from PIL import Image
        from google import genai as google_genai
        from .serializers import ToleranciaSerializer

        print("--- [DEBUG] EscanearPlanillaView EJECUTADA ---")

        # ── 1. Validar que llegó una imagen ───────────────────────────────────
        imagen = request.FILES.get('imagen') or request.FILES.get('file') or request.FILES.get('photo')
        if not imagen:
            return Response(
                {"status": "error", "message": "No se envió ninguna imagen. Usá el campo 'imagen', 'file' o 'photo'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ── 2. Validar API Key ────────────────────────────────────────────────
        if not GEMINI_API_KEY:
            return Response(
                {"status": "error", "message": "API Key de Gemini no configurada en el sistema."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # ── 3. Comprimir imagen para reducir payload ──────────────────────
            try:
                img = Image.open(imagen)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format='JPEG', quality=85)
                img_bytes = buf.getvalue()
            except Exception as img_err:
                traceback.print_exc()
                return Response(
                    {"status": "error", "message": f"Error al leer la imagen: {str(img_err)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # ── 4. Llamar a Gemini para extraer datos de la planilla ──────────
            prompt = """
Sos un experto en lectura de planillas de control de calidad industrial.
Analizá esta imagen y extraé ÚNICAMENTE los datos en formato JSON válido, sin bloques markdown.

Estructura esperada:
{
  "op_num": "Número de Orden de Producción (solo dígitos, sin texto)",
  "cliente": "Nombre del cliente, o vacío si no se encuentra",
  "proyecto": "Nombre del proyecto, o vacío",
  "articulo": "Nombre del artículo, o vacío",
  "proceso": "Proceso o denominación, o vacío",
  "mediciones": [
    {
      "nombre_control": "Nombre del parámetro o cota medida (texto exacto del encabezado de fila)",
      "nominal": "Valor nominal numérico o '-' si no hay",
      "tolerancia": "Texto de tolerancia (ej: ±0.1, +0.2/-0.1) o vacío",
      "valores_por_pieza": {
        "1": "valor numérico o estado (OK/NOK) medido para la pieza 1",
        "2": "valor numérico o estado (OK/NOK) medido para la pieza 2",
        "3": "valor numérico o estado (OK/NOK) medido para la pieza 3, y así sucesivamente para TODAS las piezas presentes..."
      }
    }
  ]
}

Reglas importantes:
- op_num: solo el número, sin "OP", sin "N°", sin texto extra.
- nombre_control: copialo exactamente como aparece en la planilla.
- MATRIZ DE MEDICIONES: Analiza meticulosamente la tabla o matriz principal de la planilla. Debes extraer TODAS las columnas de números de piezas presentes en la hoja (Pieza 1, 2, 3, etc.).
- valores_por_pieza: Incluye el valor numérico exacto o el estado PNP (ej. OK, NOK, Acep, Rech) anotado (a mano o impreso) para cada control en cada pieza. Si una celda está vacía o es ilegible, no la incluyas para ese número de pieza.
- Los valores numéricos usá punto decimal (no coma). Ej: "12.5", no "12,5".
- Devolvé SOLO el JSON puro. Sin texto adicional, sin ```json, sin explicaciones.
"""
            try:
                from google import genai as google_genai
                from google.genai import types as genai_types

                client = google_genai.Client(api_key=GEMINI_API_KEY)

                # Pasar la imagen como bytes inline (formato que acepta el nuevo SDK)
                image_part = genai_types.Part.from_bytes(
                    data=img_bytes,
                    mime_type="image/jpeg",
                )

                try:
                    gemini_response = client.models.generate_content(
                        model='gemini-3.6-flash',
                        contents=[prompt, image_part],
                    )
                except Exception as model_err:
                    import traceback
                    err_str = str(model_err).lower()
                    print(f"[DEBUG] Falló gemini-3.6-flash: {model_err}. Evaluando respaldo...")
                    
                    if "503" in err_str or "unavailable" in err_str or "server" in err_str or "quota" in err_str or "overloaded" in err_str:
                        print("[DEBUG] Error por alta demanda. Intentando con modelo de respaldo gemini-1.5-flash...")
                        try:
                            gemini_response = client.models.generate_content(
                                model='gemini-1.5-flash',
                                contents=[prompt, image_part],
                            )
                        except Exception as fallback_err:
                            print("--- [ERROR EN GEMINI BACKUP] ---")
                            print(traceback.format_exc())
                            return Response(
                                {"status": "error", "message": "Los servidores de IA están ocupados temporalmente. Por favor, intentá de nuevo en unos momentos."},
                                status=status.HTTP_503_SERVICE_UNAVAILABLE
                            )
                    else:
                        raise model_err

                raw_text = gemini_response.text.strip()
                print(f"[DEBUG] Respuesta Gemini (raw): {raw_text[:500]}")
            except Exception as api_err:
                import traceback
                print("--- [ERROR EN GEMINI] ---")
                print(traceback.format_exc())
                if "503" in str(api_err) or "unavailable" in str(api_err).lower():
                    msg = "Los servidores de IA están ocupados temporalmente. Por favor, intentá de nuevo en unos momentos."
                    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
                else:
                    msg = f"Error al llamar a Gemini: {str(api_err)}"
                    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
                return Response(
                    {"status": "error", "message": msg},
                    status=status_code
                )

            # ── 5. Parsear el JSON que devolvió Gemini ────────────────────────
            # Limpiar posibles bloques markdown residuales
            clean = raw_text
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[-1]
            if clean.endswith("```"):
                clean = clean.rsplit("```", 1)[0]
            clean = clean.strip()

            try:
                gemini_data = json.loads(clean)
            except json.JSONDecodeError as parse_err:
                print(f"[DEBUG] JSON inválido de Gemini: {clean}")
                return Response(
                    {"status": "error", "message": f"Gemini no devolvió JSON válido: {str(parse_err)}", "raw": clean},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            op_num_raw = gemini_data.get("op_num", "")
            mediciones_gemini = gemini_data.get("mediciones", [])
            print(f"[DEBUG] OP detectada: {op_num_raw} | Controles detectados: {len(mediciones_gemini)}")

            # ── 6. Buscar o Crear la Planilla en la BD usando el OP leído ─────────────
            with transaction.atomic():
                planilla = None
                op_int = 0
                if op_num_raw:
                    try:
                        op_int = int(str(op_num_raw).strip())
                        planilla = PlanillaMedicion.objects.filter(num_op=op_int).first()
                    except (ValueError, TypeError):
                        pass

                from .models import Cliente, Articulo, Proceso, Control, Tolerancia
                
                def get_or_create_rel(model_class, name):
                    if not name: return None
                    obj = model_class.objects.filter(nombre__iexact=name.strip()).first()
                    if not obj:
                        obj = model_class.objects.create(nombre=name.strip())
                    return obj

                cliente_obj = get_or_create_rel(Cliente, gemini_data.get("cliente", ""))
                articulo_obj = get_or_create_rel(Articulo, gemini_data.get("articulo", ""))
                proceso_obj = get_or_create_rel(Proceso, gemini_data.get("proceso", ""))
                proyecto_str = gemini_data.get("proyecto", "OCR App")

                if planilla is None:
                    from django.utils import timezone
                    planilla = PlanillaMedicion.objects.create(
                        num_op=op_int,
                        proyecto=proyecto_str if proyecto_str else "OCR App",
                        cliente=cliente_obj,
                        articulo=articulo_obj,
                        proceso=proceso_obj,
                        fecha_elaborador=timezone.now().date(),
                        observaciones='Generado desde app móvil via AI OCR'
                    )
                else:
                    if not planilla.cliente and cliente_obj: planilla.cliente = cliente_obj
                    if not planilla.articulo and articulo_obj: planilla.articulo = articulo_obj
                    if not planilla.proceso and proceso_obj: planilla.proceso = proceso_obj
                    if (not planilla.proyecto or planilla.proyecto in ['OCR App', 'OCR Import']) and proyecto_str:
                        planilla.proyecto = proyecto_str
                    planilla.save()

                # Crear/Actualizar tolerancias y controles
                import re
                for idx, item in enumerate(mediciones_gemini):
                    nombre_control = item.get("nombre_control", "").strip()
                    if not nombre_control: continue
                    control_obj = get_or_create_rel(Control, nombre_control)

                    # Verificar si hay valores PNP
                    valores_por_pieza = item.get("valores_por_pieza", {})
                    has_pnp_values = any(str(v).strip().upper().startswith(x) for x in ['OK', 'PAS', 'ACEP', 'NOK', 'FAL', 'FAI'] for v in valores_por_pieza.values())
                    if has_pnp_values and not control_obj.pnp: 
                        control_obj.pnp = True
                        control_obj.save()

                    nom_str = str(item.get("nominal", "0")).replace(',', '.')
                    nom_nums = re.findall(r"[-+]?\d*\.\d+|\d+", nom_str)
                    nominal_val = float(nom_nums[0]) if nom_nums else 0.0
                    
                    tol_str_clean = str(item.get("tolerancia", "")).replace(',', '.').strip()
                    tol_str_clean = re.sub(r'([-+])\s+(\d)', r'\1\2', tol_str_clean)
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

                    Tolerancia.objects.update_or_create(
                        planilla=planilla,
                        control=control_obj,
                        defaults={
                            'nominal': nominal_val,
                            'minimo': limit_min,
                            'maximo': limit_max,
                            'posicion': idx + 1
                        }
                    )

            # ── 7. Cargar cotas reales de la BD ──────────────────────────────
            tolerancias = Tolerancia.objects.filter(planilla=planilla).select_related('control').order_by('posicion')
            cotas_data = ToleranciaSerializer(tolerancias, many=True).data

            # ── 8. Mapear valores de Gemini a los IDs reales de Tolerancia ───
            # Estrategia: comparar nombre_control de Gemini con control.nombre de BD
            # usando búsqueda insensible a mayúsculas/acentos
            import unicodedata

            def normalizar(texto):
                """Quita acentos y pasa a minúsculas para comparar."""
                nfkd = unicodedata.normalize('NFKD', str(texto))
                sin_acentos = ''.join(c for c in nfkd if not unicodedata.combining(c))
                return sin_acentos.lower().strip()

            # Construir lookup: nombre_normalizado → tolerancia_id
            nombre_a_tolerancia_id = {}
            for cota in cotas_data:
                nombre_norm = normalizar(cota['control']['nombre'])
                nombre_a_tolerancia_id[nombre_norm] = cota['id']

            # Mapear valores de Gemini → mediciones_valores
            # Formato esperado: { "pieza_str": { tolerancia_id: valor_str } }
            mediciones_valores = {}

            for item in mediciones_gemini:
                nombre_gemini = normalizar(item.get("nombre_control", ""))
                tol_id = nombre_a_tolerancia_id.get(nombre_gemini)

                if tol_id is None:
                    # Intentar coincidencia parcial (Gemini a veces abrevia)
                    for nombre_bd, tid in nombre_a_tolerancia_id.items():
                        if nombre_gemini in nombre_bd or nombre_bd in nombre_gemini:
                            tol_id = tid
                            break

                if tol_id is None:
                    print(f"[DEBUG] Control '{item.get('nombre_control')}' no encontrado en BD. Omitiendo.")
                    continue

                valores_por_pieza = item.get("valores_por_pieza", {})
                for pieza_str, valor in valores_por_pieza.items():
                    valor_limpio = str(valor).replace(",", ".").strip()
                    if not valor_limpio:
                        continue
                    if pieza_str not in mediciones_valores:
                        mediciones_valores[pieza_str] = {}
                    mediciones_valores[pieza_str][tol_id] = valor_limpio

            piezas_registradas = sorted(mediciones_valores.keys(), key=lambda x: int(x))

            # ── 9. Devolver en el mismo formato que CotasPlanillaAPIView ─────
            return Response({
                "status": "success",
                "message": "Planilla procesada correctamente con IA.",
                # Campos que MedicionesScreen espera en opData:
                "planilla_id": planilla.id,
                "op_num": planilla.num_op,
                "proyecto": planilla.proyecto,
                "cliente": planilla.cliente.nombre if planilla.cliente else None,
                "cotas": cotas_data,
                "piezas_registradas": piezas_registradas,
                "mediciones_valores": mediciones_valores,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            traceback.print_exc()
            return Response(
                {"status": "error", "message": f"Error interno del servidor: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
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
