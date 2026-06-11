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
        Eres un sistema experto en lectura de Planillas de Inspección de ABBAMAT.
        Tu objetivo es extraer la tabla de controles técnicos con precisión quirúrgica.
        
        INSTRUCCIONES OBLIGATORIAS:
        1. La tabla tiene estas columnas: COTA | DETALLE | SOLICITADO | TOL. | FREC. | INSTRUMENTO | [valores por pieza]
        2. La columna COTA contiene un número correlativo (1, 2, 3, 4, ...). Es OBLIGATORIO extraer este número.
        3. SOLO extrae filas donde la columna COTA tenga un número entero (1, 2, 3...). 
           - Filas como "Reporte Equal", "FECHA", "OPERARIO", "SUPERVISOR", "CONTROL CALIDAD" NO tienen cota numérica. IGNÓRALAS.
           - Anotaciones del dibujo como "E/ Aguj.", "Aguj. Inclin." NO pertenecen a la tabla. IGNÓRALAS.
        4. Si el PDF tiene varias páginas con la misma tabla, NO repitas filas. Cada número de COTA aparece UNA SOLA VEZ.
        5. Extrae los valores numéricos de cada pieza tal como están escritos.

        Responde ÚNICAMENTE este JSON:
        {
          "header": {"op": "", "proyecto": "", "cliente": "", "articulo": "", "denominacion": "", "operacion": ""},
          "piezas": [1, 2, 5, 7, 8, 11, 14, 17, 20, 23],
          "matrix": [
            {
              "cota": "1",
              "control": "Ø EXTERIOR",
              "nominal": "20.80",
              "tolerancia": "±0.10",
              "instrumento": "CAD 40",
              "valores": ["20.79", "20.80", "20.80", ...]
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
        
        def clean_value(v):
            if v is None: return ""
            if isinstance(v, dict):
                v = v.get('valor') or v.get('val') or v.get('value') or ""
            s = str(v).strip().replace(',', '.')
            if s.lower() in ['none', 'null', 'nan', 'undefined', 'n/a', '-']: return ""
            # Si contiene basura como "{'val':...", intentar limpiar
            if '{' in s: return ""
            return s

        merged_matrix = {}
        target_size = len(data.get('piezas', []))
        draw_noise = ["E/AGUJ", "AGUJINCLIN", "COTAS", "PLANOS", "REPORTE", "EQUAL", "FIRMA", "ACLARACION"]

        for row in data.get('matrix', []):
            # Normalización de Cota
            raw_cota = str(row.get('cota', '')).strip().replace('.', '').replace(')', '')
            raw_name = str(row.get('control', '')).upper()
            nominal = str(row.get('nominal', '0')).replace(',', '.')
            
            # Limpiar nombre para filtros
            clean_name = re.sub(r'[^A-ZØ]', '', raw_name)
            
            # Filtro de ruido: Ignorar si es término de dibujo o si el nombre está vacío
            if any(noise in clean_name for noise in draw_noise) or len(clean_name) < 2:
                continue
            
            # REGLA ESTRICTA: Si no hay cota numérica, la fila es ruido. Se descarta.
            if not raw_cota.isdigit():
                continue

            key = f"COTA_{raw_cota}"

            # Procesar valores
            raw_vals = row.get('valores', [])
            cleaned_vals = [clean_value(v) for v in raw_vals]

            if key not in merged_matrix:
                row['valores'] = cleaned_vals
                merged_matrix[key] = row
            else:
                # Si la cota ya existe (misma tabla en otra página), nos quedamos con la que tenga más datos
                existing = merged_matrix[key]
                count_existing = len([v for v in existing['valores'] if v])
                count_new = len([v for v in cleaned_vals if v])
                
                if count_new > count_existing:
                    row['valores'] = cleaned_vals
                    merged_matrix[key] = row
                else:
                    # Completar huecos
                    for i in range(min(len(existing['valores']), len(cleaned_vals), target_size)):
                        if not existing['valores'][i] and cleaned_vals[i]:
                            existing['valores'][i] = cleaned_vals[i]

        # Formatear lista final ordenada por número de cota
        def sort_key(k):
            if k.startswith("COTA_"):
                try: return int(k.replace("COTA_", ""))
                except: return 999
            return 888

        final_rows = []
        for k in sorted(merged_matrix.keys(), key=sort_key):
            row = merged_matrix[k]
            # Ajustar longitud de valores al número de piezas
            vals = row['valores']
            if len(vals) < target_size:
                vals.extend([""] * (target_size - len(vals)))
            else:
                row['valores'] = vals[:target_size]
            final_rows.append(row)

        # ── DESAMBIGUACIÓN DE NOMBRES DUPLICADOS ──────────────────────────────
        # Si hay dos o más controles con el mismo nombre (ej: tres "ALT. PARCIAL"),
        # los renombra a "ALT. PARCIAL 1", "ALT. PARCIAL 2", "ALT. PARCIAL 3"
        # para que se guarden con nombres únicos en el plan maestro.
        from collections import Counter
        name_count = Counter(row['control'] for row in final_rows)
        name_seen  = {}
        for row in final_rows:
            name = row['control']
            if name_count[name] > 1:
                name_seen[name] = name_seen.get(name, 0) + 1
                row['control'] = f"{name} {name_seen[name]}"

        data['matrix'] = final_rows
        return data
    else:
        raise ValueError("La IA respondió pero no en formato JSON válido")
