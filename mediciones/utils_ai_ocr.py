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
        Tu objetivo es extraer con PRECISION QUIRÚRGICA los datos técnicos de la imagen adjunta. 
        
        REGLAS DE ORO:
        - **NÚMEROS DE PIEZAS REALES**: Extrae los números de piezas EXACTOS que aparecen en la fila 'NÚMERO DE PIEZAS' (ej: 18, 20, 22...). NUNCA inventes una secuencia 1, 2, 3... si no está en el papel.
        - **ALINEACIÓN FILA/COLUMNA**: Asegúrate de que cada medición (valor) corresponda exactamente a la columna de su número de pieza.
        - **MÚLTIPLES SECCIONES**: Este formulario puede tener la tabla dividida en dos o más bloques. Debes concatenar los resultados. Por ejemplo, si el control "Ancho" aparece arriba para las piezas 1-10 y abajo para las piezas 11-20, el resultado debe ser un único control "Ancho" con los 20 valores.
        - **VALORES VACÍOS**: Si una celda está vacía, devuelve un string vacío "". No asumas valores previos.
        - **COTA vs DETALLE**: Ignora la columna COTA. Extrae el nombre del control solo de DETALLE.
        - **VALORES CUALITATIVOS**: Captura "OK", "NOK", "PASA", "FALLA" exactamente.

        INSTRUCCIONES DE EXTRACCIÓN:
        1. HEADER: Extrae Nro OP (ej: 85480), Proyecto (ej: 240+40), Cliente, Artículo, Denominación y Operación.
        2. PIEZAS: Crea una lista única y ordenada de todos los números de piezas identificados en todas las secciones ('NÚMERO DE PIEZAS').
        3. MATRIX:
           - "control": Nombre limpio (sin números de índice).
           - "nominal": Valor numérico o "S/N".
           - "tolerancia": "+0.10 / -0.20" o "± 0.05".
           - "valores": Una lista de strings que coincida EN ORDEN con la lista global de 'piezas'.
        4. Si un valor está corregido a mano, prioriza el valor escrito a mano.

        Responde ÚNICAMENTE con este JSON:
        {
          "header": {"op": "", "proyecto": "", "cliente": "", "articulo": "", "denominacion": "", "operacion": ""},
          "piezas": [18, 20, 22, 27, 40, ...], 
          "matrix": [
            {
              "control": "Nombre del Control",
              "nominal": "0.00",
              "tolerancia": "+0.00 / -0.00",
              "instrumento": "MIC / CAP / ...",
              "valores": ["4.05", "4.05", "4.06", ...] 
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
            model = genai.GenerativeModel(
                model_name=primary_model,
                generation_config={"temperature": 0.1, "top_p": 0.95, "top_k": 0}
            )
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
                    model = genai.GenerativeModel(
                        model_name=m_obj.name,
                        generation_config={"temperature": 0.1, "top_p": 0.95, "top_k": 0}
                    )
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
