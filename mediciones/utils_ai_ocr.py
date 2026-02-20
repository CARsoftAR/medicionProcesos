import google.generativeai as genai
import os
import json
import re
import base64

# --- CONFIGURACIÓN ---
API_KEY_HARDCODED = None
API_KEY = os.environ.get("GOOGLE_API_KEY") or API_KEY_HARDCODED

def configure_genai(api_key):
    """Configura la librería con la key proporcionada."""
    global API_KEY
    API_KEY = api_key
    genai.configure(api_key=API_KEY)

def extract_data_with_gemini(pdf_path, mime_type="application/pdf", api_key=None):
    """
    Usa Google Gemini para extraer datos estructurados de un PDF/Imagen.
    Implementa un sistema de fallback para evitar límites de cuota (429).
    """
    selected_key = api_key or API_KEY
    if not selected_key:
        raise ValueError("API Key de Google Gemini no configurada.")

    genai.configure(api_key=selected_key)

    try:
        print(f"[AI-OCR] Procesando archivo: {pdf_path}")
        
        with open(pdf_path, "rb") as f:
            doc_data = f.read()
            doc_base64 = base64.b64encode(doc_data).decode('utf-8')

        prompt = """
        Eres un sistema experto en extracción de datos de Planillas de Inspección de ABBAMAT.
        Tu objetivo es extraer con precisión quirúrgica los datos técnicos de la imagen adjunta.
        
        INSTRUCCIONES DE EXTRACCIÓN:
        1. HEADER: Extrae Nro OP (ej: 46676), Proyecto (ej: 25-069), Cliente, Artículo y Denominación.
        2. PIEZAS: Identifica todos los números de piezas únicos en la fila de 'NÚMERO DE PIEZAS'.
        3. MATRIX (MERGE OBLIGATORIO):
           - Si la planilla tiene dos partes o secciones que repiten los mismos CONTROLES para piezas diferentes, DEBES UNIRLOS en una sola fila.
           - El campo "valores" debe contener todas las mediciones de todas las piezas identificadas para ese control, en orden.
           - NO repitas controles. Si el control "Ø Exterior" aparece dos veces, agrupa todos sus valores en un solo objeto.
        4. Si un valor está borroneado, usa el corregido.
        5. TOLERANCIAS (CRÍTICO - LEER CON ATENCIÓN):
           - El formato "-0,20-0,50" NO es un rango, son dos límites NEGATIVOS. 
           - Significa: Límite Superior = -0.20 y Límite Inferior = -0.50.
           - Igualmente "-0,20-0,10" -> "-0.20 / -0.10".
           - El segundo guion es un signo negativo, no un separador.
           - Formatea la salida "tolerancia" siempre como "LimSup / LimInf" (ej: "-0.20 / -0.50").

        Responde ÚNICAMENTE con este JSON:
        {
          "header": {"op": "", "proyecto": "", "cliente": "", "articulo": "", "denominacion": "", "operacion": ""},
          "piezas": [205, 215, ...],
          "matrix": [
            {
              "control": "Ø Exterior",
              "nominal": "52.00",
              "tolerancia": "-0.20 / -0.50",
              "instrumento": "MIC 8",
              "valores": ["51.96", "51.95", ...]
            }
          ]
        }
        """

        doc_part = {
            "mime_type": mime_type,
            "data": doc_base64
        }

        # 2. Selección de Modelo: Estrategia Definitiva
        # Paso 1: Intentar Directamente el modelo más eficiente (Standard)
        # Esto ahorra la llamada a list_models() si todo va bien.
        primary_model = "gemini-1.5-flash"
        errors_log = []
        
        try:
            print(f"[AI-OCR] Intentando modelo primario: {primary_model}...")
            model = genai.GenerativeModel(primary_model)
            response = model.generate_content([prompt, doc_part])
            if response and response.text:
                 # ÉXITO DIRECTO
                 return process_gemini_response(response)
        except Exception as e:
            err_str = str(e)
            print(f"[AI-OCR] Falló primario {primary_model}: {err_str[:100]}...")
            errors_log.append(f"{primary_model}: {err_str}")

        # Paso 2: Fallback Dinámico (Preguntar a la API qué tiene realmente)
        # Si falló el hardcoded, consultamos list_models para no adivinar nombres.
        try:
            print("[AI-OCR] Iniciando búsqueda dinámica de modelos disponibles...")
            all_models = list(genai.list_models())
            
            # Filtrar solo los que generan contenido
            valid_models = [
                m for m in all_models 
                if 'generateContent' in m.supported_generation_methods
            ]
            
            # Ordenar por preferencia: Flash > Latest > Pro > Otros
            def model_priority(m):
                name = m.name.lower()
                if '1.5-flash' in name: return 0
                if 'flash' in name: return 1
                if 'latest' in name: return 2
                if 'pro' in name: return 3
                return 4
            
            valid_models.sort(key=model_priority)
            
            if not valid_models:
                raise ValueError("La API Key es válida pero no tiene acceso a ningún modelo con 'generateContent'.")

            print(f"[AI-OCR] Modelos encontrados: {[m.name for m in valid_models]}")

            for m_obj in valid_models:
                # No reintentar el que ya falló en el Paso 1
                if primary_model in m_obj.name: 
                    continue
                
                try:
                    print(f"[AI-OCR] Intentando fallback con: {m_obj.name}...")
                    model = genai.GenerativeModel(m_obj.name)
                    response = model.generate_content([prompt, doc_part])
                    
                    if response and response.text:
                         print(f"[AI-OCR] RECUPERADO con modelo: {m_obj.name}")
                         return process_gemini_response(response)
                         
                except Exception as e:
                    err_str = str(e)
                    print(f"[AI-OCR] Falló {m_obj.name}: {err_str[:50]}...")
                    errors_log.append(f"{m_obj.name}: {err_str}")
                    continue

        except Exception as listing_error:
            errors_log.append(f"ListModels Error: {str(listing_error)}")

        # --- DIAGNÓSTICO FINAL ---
        full_log = " | ".join(errors_log)
        if "429" in full_log or "Quota" in full_log:
             raise ValueError("LÍMITE DE CUOTA DIARIO: Se agotaron los recursos gratuitos de la IA. Por favor intenta mañana.")
        
        raise ValueError(f"No se pudo procesar el documento. Errores: {full_log[:300]}...")

    except Exception as e:
        print(f"!!! Error CRÍTICO en Gemini OCR: {e}")
        raise e

def process_gemini_response(response):
    response_text = response.text.strip()
    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
    if json_match:
        data = json.loads(json_match.group(0))
        
        # POST-PROCESAMIENTO
        def normalize_name(n):
            return re.sub(r'^\d+[\.\)\-\s]+', '', str(n)).strip().upper()

        merged_matrix = {}
        for row in data.get('matrix', []):
            raw_name = row.get('control', '')
            norm_name = normalize_name(raw_name)
            if not norm_name: continue
            if norm_name not in merged_matrix:
                merged_matrix[norm_name] = row
            else:
                new_vals = row.get('valores', [])
                merged_matrix[norm_name]['valores'].extend(new_vals)
        
        data['matrix'] = list(merged_matrix.values())
        return data
    else:
        raise ValueError("La IA respondió pero no en formato JSON válido")
