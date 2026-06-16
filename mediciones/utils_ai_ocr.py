import os
import json
import base64
import logging
import google.generativeai as genai
import fitz

logger = logging.getLogger(__name__)

def get_base64_from_file(file_path, mime_type):
    """
    Convierte un PDF (primera página) o una imagen directamente a Base64.
    """
    if mime_type == "application/pdf":
        doc = fitz.open(file_path)
        page = doc.load_page(0)
        # Calidad ajustada para que Gemini pueda leer bien los trazos
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img_bytes = pix.tobytes("png")
        return base64.b64encode(img_bytes).decode("utf-8"), "image/png"
    else:
        # Si ya es una imagen
        with open(file_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8"), mime_type

def extract_data_with_gemini(pdf_path, mime_type="application/pdf", api_key=None, model_name="gemini-1.5-flash"):
    """
    Motor OCR 100% IA Pura usando Google Generative AI (Gemini).
    Extrae los datos de la planilla en un JSON estructurado.
    """
    if not api_key:
        raise ValueError("No se proporcionó una API Key válida para Gemini.")

    genai.configure(api_key=api_key)

    try:
        base64_img, actual_mime = get_base64_from_file(pdf_path, mime_type)
    except Exception as e:
        raise ValueError(f"Error al procesar el archivo local antes de enviarlo a la IA: {e}")

    prompt = """
    Actúa como un experto en control de calidad industrial. Tu tarea es extraer valores numéricos de una planilla de control de piezas mecanizadas.

    Devuelve un JSON puro sin explicaciones, asegurando que matrix sea una lista de objetos donde cada objeto contenga la clave valores con los datos de cada pieza identificados por su número de columna.
    
    Estructura esperada:
    {
      "header": {
        "cliente": "string",
        "articulo": "string",
        "op": "string",
        "proyecto": "string",
        "denominacion": "string",
        "operacion": "string",
        "fecha": "string",
        "inspector": "string"
      },
      "piezas": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
      "matrix": [
        {
          "control": "nombre del control o cota",
          "nominal": "valor nominal",
          "tolerancia": "tolerancia",
          "instrumento": "instrumento usado",
          "valores": [ "val1", "val2", "val3", "val4", "val5", "val6", "val7", "val8", "val9", "val10" ]
        }
      ]
    }

    Recuerda que la planilla tiene 10 piezas horizontales y los controles están definidos en el archivo. No intentes inferir encabezados nuevos, usa los predefinidos:
    1. Ø INT 92
    2. Ø INT 60,5
    3. Ø RAN F/INT 67,5
    4. ALT INT 12,15
    5. AL INT 4
    6. Ø INT 37
    7. Ø EXT 136
    8. ALT TOTAL 45
    9. RAN.F. 2.5
    10. ALT RAN.F. 1,25

    REGLAS CRÍTICAS:
    - Los valores en la matriz deben seguir estrictamente el orden de los controles definidos en controles_maestros. No omitas filas ni columnas aunque el valor sea 0 o esté vacío; usa '0' o 'null' para mantener la integridad de la estructura JSON.
    - Prioriza la lectura de los números escritos a mano en los casilleros de medición. Si un número es ilegible, coloca una cadena vacía pero mantén la posición en el array.
    """

    model = genai.GenerativeModel(model_name)
    
    try:
        response = model.generate_content([
            {'mime_type': actual_mime, 'data': base64_img},
            prompt
        ])
        
        # Limpieza de la respuesta para evitar errores de parseo
        text_resp = response.text.strip()
        if text_resp.startswith('```json'):
            text_resp = text_resp[7:]
        if text_resp.startswith('```'):
            text_resp = text_resp[3:]
        if text_resp.endswith('```'):
            text_resp = text_resp[:-3]
            
        text_resp = text_resp.strip()
        
        datos = json.loads(text_resp)
        return datos

    except Exception as e:
        logger.error(f"Error en Gemini API: {e}")
        # Retornamos el error hacia la vista para que no se inventen datos
        raise Exception(f"Fallo en la conexión con Gemini o JSON inválido: {str(e)}")