import google.generativeai as genai
import os
import json
import re
import base64

# --- CONFIGURACIÓN ---
# Puedes poner tu API Key aquí manualmente si el sistema de perfiles falla:
# API_KEY_HARDCODED = "AIza..." 
API_KEY_HARDCODED = None

API_KEY = os.environ.get("GOOGLE_API_KEY") or API_KEY_HARDCODED

def configure_genai(api_key):
    """Configura la librería con la key proporcionada."""
    global API_KEY
    API_KEY = api_key
    genai.configure(api_key=API_KEY)

def extract_data_with_gemini(pdf_path, mime_type="application/pdf", api_key=None):
    """
    Usa Google Gemini Flash para extraer datos estructurados de un PDF/Imagen.
    """
    selected_key = api_key or API_KEY
    if not selected_key:
        raise ValueError("API Key de Google Gemini no configurada.")

    genai.configure(api_key=selected_key)

    try:
        print(f"[AI-OCR] Procesando archivo: {pdf_path}")
        
        # Leer el archivo y convertir a bytes base64
        with open(pdf_path, "rb") as f:
            doc_data = f.read()
            doc_base64 = base64.b64encode(doc_data).decode('utf-8')

        # 1. Definir el prompt con el contexto del éxito en la web
        prompt = """
        Eres un sistema experto en extracción de datos de Planillas de Inspección de ABBAMAT.
        Tu objetivo es extraer con precisión quirúrgica los datos técnicos de la imagen adjunta.
        
        CONTEXTO DEL DOCUMENTO:
        - Es una 'ORDEN DE PROCESO' con cabecera (Proyecto, OP, Cliente, etc.).
        - Tiene una tabla de controles con columnas 'COTA', 'DETALLE', 'SOLICITADO' (Nominal), 'TOLERANCIA' e 'INSTRUMENTO'.
        - A la derecha, hay columnas manuscritas con los números de piezas (205, 215, 225...) y debajo sus mediciones reales.

        INSTRUCCIONES DE EXTRACCIÓN:
        1. HEADER: Extrae Nro OP (ej: 46676), Proyecto (ej: 25-069), Cliente, Artículo y Denominación.
        2. PIEZAS: Identifica todos los números de piezas en la fila de 'NÚMERO DE PIEZAS' (ej: 205, 215, 225, 235, 245, 255, 265, 266...).
        3. MATRIX: Para cada fila de la tabla de control (ej: Ø Exterior, Largo Cilindrado, Largo Total):
           - Extrae el nombre, valor nominal, tolerancia e instrumento.
           - Extrae los VALORES REALES escritos debajo de cada número de pieza correspondiente.
        4. Si un valor está borroneado o tachado, pero se lee el nuevo (ej: 125 corregido), usa el corregido.

        Responde ÚNICAMENTE con este JSON:
        {
          "header": {"op": "", "proyecto": "", "cliente": "", "articulo": "", "denominacion": "", "operacion": ""},
          "piezas": [205, 215, ...],
          "matrix": [
            {
              "control": "Ø Exterior",
              "nominal": "52.00",
              "tolerancia": "+0.0 / -0.1",
              "instrumento": "MIC 8",
              "valores": ["51.96", "51.95", ...]
            }
          ]
        }
        """

        # Crear la parte del documento para Gemini (multimodal)
        doc_part = {
            "mime_type": mime_type,
            "data": doc_base64
        }

        # 2. Selección de Modelo Dinámica
        # Basado en tus logs, el sistema no encuentra 'gemini-1.5-flash'.
        # Vamos a buscar dinámicamente qué modelo 'flash' tienes disponible.
        try:
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            print(f"[AI-OCR] Modelos disponibles en tu cuenta: {available_models}")
            
            # Buscamos el primero que tenga 'flash' (preferiblemente 1.5 o 2.0)
            model_name = next((m for m in available_models if 'flash' in m), "models/gemini-pro")
            
            print(f"[AI-OCR] Usando modelo detectado: {model_name}")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content([prompt, doc_part])
            
            if response and response.text:
                print(f"[AI-OCR] ÉXITO con: {model_name}")
            else:
                raise ValueError("Respuesta vacía de la IA.")
                
        except Exception as e:
            print(f"[AI-OCR] Error en selección dinámica: {e}")
            raise ValueError(f"Falla de Modelos: {e}")

        if not response or not hasattr(response, 'text') or not response.text:
            raise ValueError("No se pudo obtener respuesta de Gemini.")
        
        # 3. Limpieza y extracción robusta de JSON
        response_text = response.text.strip()
        print(f"[AI-OCR] Respuesta recibida (longitud {len(response_text)})")
        
        # Intentar extraer el bloque JSON incluso si hay texto basura alrededor
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            data = json.loads(json_str)
            return data
        else:
            print(f"[AI-OCR] No se encontró JSON en: {response_text[:200]}...")
            raise ValueError("La IA no generó un formato JSON válido.")

    except Exception as e:
        print(f"!!! Error CRÍTICO en Gemini OCR: {e}")
        raise e
