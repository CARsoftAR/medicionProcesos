import re
import fitz
import logging
import unicodedata
import cv2
import numpy as np
import pytesseract

logger = logging.getLogger(__name__)

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Tabla de caracteres mal interpretados por conversión vectorial
_REEMPLAZOS = [
    (r'\b27\b',  'Ø'),
    (r'\bO\b',   'Ø'),
    (r'1\/2"',   '1/2"'),
    (r'3\/8"',   '3/8"'),
]

def _sanitizar_texto(txt):
    if not txt: return ""
    txt = unicodedata.normalize("NFC", txt)
    txt = txt.replace('\u2300', 'Ø').replace('\u00f8', 'Ø').replace('\u00d8', 'Ø')
    return txt.strip()

def _campo_tras_etiqueta(texto_lineas, etiqueta_regex, parar_en=None):
    stop = parar_en if parar_en else r'$'
    pat = etiqueta_regex + r'\s*:?\s*(.+?)(?=' + stop + r'|\n|$)'
    m = re.search(pat, texto_lineas, re.IGNORECASE | re.MULTILINE)
    if not m: return ""
    val = _sanitizar_texto(m.group(1))
    val = re.sub(r'\s{2,}', ' ', val).strip()
    return val

def _ocr_celda_manuscrita(img_celda, whitelist='0123456789,.-okOK', psm=7):
    """Aplica OCR sobre una celda recortada esperando un número o 'OK'."""
    if img_celda is None or img_celda.size == 0:
        return ""
    gray = cv2.cvtColor(img_celda, cv2.COLOR_BGR2GRAY)
    # Escalar para mejorar lectura de birome (2.5x suele ser mejor para birome que 3x)
    gray = cv2.resize(gray, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)
    
    # Adaptive threshold funciona mejor para celdas irregulares
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 9)
    
    # PSM configurable (7 para línea, 8 para palabra simple)
    txt = pytesseract.image_to_string(
        thresh, 
        config=f'--psm {psm} -c tessedit_char_whitelist={whitelist}'
    ).strip()
    
    txt_lower = txt.lower()
    if "ok" in txt_lower:
        return "OK"
    
    if re.search(r'\d', txt):
        val = re.sub(r'^[^\d+\-]+', '', txt)
        val = re.sub(r'[^\d]+$', '', val)
        return val.strip()
    return ""

def _detectar_y_renglones_grilla(gray_img, y_min, y_max):
    """
    Usa morfología para detectar las líneas horizontales de la grilla
    en la zona de datos (entre y_min y y_max) y devuelve las franjas Y.
    El índice 0 de la franja es el encabezado de número de piezas.
    """
    zona = gray_img[y_min:y_max, :]
    _, bw = cv2.threshold(zona, 180, 255, cv2.THRESH_BINARY_INV)
    H, W = bw.shape
    kh = cv2.getStructuringElement(cv2.MORPH_RECT, (W // 7, 2))
    horiz = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kh, iterations=2)
    
    proj = np.sum(horiz, axis=1) // 255
    umbral = W * 0.10
    lineas = []
    prev = 0
    for i, val in enumerate(proj):
        activo = 1 if val >= umbral else 0
        if activo and not prev:
            lineas.append(y_min + i)
        prev = activo
        
    filas = []
    # Emparejar líneas consecutivas (y0, y1)
    for i in range(1, len(lineas)):
        if lineas[i] - lineas[i-1] > 12: # Evitar líneas dobles
            filas.append((lineas[i-1], lineas[i]))
            
    return filas


def extraer_datos_de_pdf(pdf_bytes=None):
    logger.info("[HYBRID] Iniciando extracción híbrida con PyMuPDF + Tesseract...")

    vacia = {
        "header": {"op": "", "proyecto": "", "cliente": "", "articulo": "",
                   "denominacion": "", "operacion": ""},
        "piezas": [str(i) for i in range(1, 11)],
        "matrix": []
    }

    if not pdf_bytes:
        return vacia

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc.load_page(0)
        
        # ── RENDERING DE IMAGEN ──────────────────────────────────────────────
        zoom_mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=zoom_mat)
        img_array = np.frombuffer(pix.tobytes("png"), np.uint8)
        img_cv = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        H_img, W_img = img_cv.shape[:2]
        H_pdf, W_pdf = page.rect.height, page.rect.width
        scale_x = W_img / W_pdf
        scale_y = H_img / H_pdf

        # ── 1. TEXTO VECTORIAL PARA CABECERA Y ESTRUCTURA ────────────────────
        texto_con_lineas = page.get_text("text")
        texto_con_lineas = _sanitizar_texto(texto_con_lineas)
        words_raw = page.get_text("words")
        words = [{"text": _sanitizar_texto(w[4]), "x0": w[0], "y0": w[1], "x1": w[2], "y1": w[3]} 
                 for w in words_raw if w[4].strip()]

        # ── 2. PARSING DE CABECERA ───────────────────────────────────────────
        op = ""
        m_op = re.search(r'NRO\.?\s*OP\.?\s*:?\s*(\d{4,7})', texto_con_lineas, re.IGNORECASE)
        if m_op: op = m_op.group(1).strip()

        proyecto = ""
        m_proy = re.search(r'(?:N[°º\.º]?\s*)?PROYECTO\s*:?\s*(\d{2,4}-\d{2,6})', texto_con_lineas, re.IGNORECASE)
        if m_proy: proyecto = m_proy.group(1).strip()

        articulo = ""
        m_art = re.search(r'ART[IÍ]CULO\s*:?\s*([A-Z0-9][\w\-./]{2,20})', texto_con_lineas, re.IGNORECASE)
        if m_art: articulo = m_art.group(1).strip()

        cliente = _campo_tras_etiqueta(texto_con_lineas, r'CLIENTE', r'MÁQUINA|ART[IÍ]CULO|DENOMINACI|OPERACI|FECHA|PLANO')
        cli_m = re.search(r'([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ0-9\s&.\-]{0,30})', cliente, re.IGNORECASE)
        cliente = cli_m.group(1).strip() if cli_m else ""

        denominacion = _campo_tras_etiqueta(texto_con_lineas, r'DENOMINACI[OÓ]N', r'ART[IÍ]CULO|CANTIDAD|MÁQUINA|OPERACI|FECHA')
        operacion = _campo_tras_etiqueta(texto_con_lineas, r'OPERACI[OÓ]N', r'SECTOR|CANTIDAD|FECHA|PLANO|FIRMA|MÁQUINA')

        # ── 3. DETECTAR LÍMITES DE ZONA DE PIEZAS E INSTRUMENTO ──────────────
        x_instr_izquierda = None
        x_instr_derecha = None
        x_obs_izquierda = None
        y_header_tabla = None
        
        # Buscar límites de las columnas clave
        for w in words:
            if w["y0"] < H_pdf * 0.20 or w["y0"] > H_pdf * 0.80: continue
            wtl = w["text"].lower()
            if "instrument" in wtl:
                x_instr_izquierda = w["x0"]
                x_instr_derecha = w["x1"]
                y_header_tabla = w["y0"]
            if "observaci" in wtl or "bservaci" in wtl:
                x_obs_izquierda = w["x0"]

        # Valores base de PDF
        x_piezas_ini_pdf = x_instr_derecha if x_instr_derecha else W_pdf * 0.48
        x_piezas_fin_pdf = x_obs_izquierda if x_obs_izquierda else W_pdf * 0.83
        x_inst_ini_pdf   = x_instr_izquierda if x_instr_izquierda else W_pdf * 0.38
        
        # Conversión a Píxeles
        x_ini_px = int(x_piezas_ini_pdf * scale_x)
        x_fin_px = int(x_piezas_fin_pdf * scale_x)
        y_header_px = int((y_header_tabla - 5) * scale_y) if y_header_tabla else int(H_img * 0.35)
        
        # ── 4. DETECTAR RENGLONES Y CABECERA DE PIEZAS ───────────────────────
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        y_datos_fin_px = int(H_img * 0.75)
        
        renglones_y = _detectar_y_renglones_grilla(gray, y_header_px, y_datos_fin_px)
        
        # Si no hay renglones suficientes, matemática fallback
        if len(renglones_y) < 7:
            logger.warning("[HYBRID] Fallback a división matemática de renglones.")
            alto_tabla = y_datos_fin_px - y_header_px
            alto_fila = alto_tabla // 8
            renglones_y = []
            base_y = y_header_px
            for i in range(8):
                renglones_y.append((base_y + i * alto_fila, base_y + (i+1) * alto_fila))

        cols = 8
        ancho_col = (x_fin_px - x_ini_px) // cols

        # ── 5. EXTRAER NÚMEROS REALES DE LAS PIEZAS ──────────────────────────
        # El primer renglón detectado (y0, y1) suele ser el que contiene los números de pieza
        piezas_detectadas = []
        if len(renglones_y) > 0:
            y0_cab, y1_cab = renglones_y[0]
            for c in range(cols):
                x0_col = x_ini_px + c * ancho_col
                x1_col = x0_col + ancho_col
                
                # Márgenes más estrictos para cabecera, para evitar leer líneas verticales como '3' o '1'
                margen_x = int(ancho_col * 0.25)
                margen_y = int((y1_cab - y0_cab) * 0.20)
                
                celda_img = img_cv[y0_cab + margen_y : y1_cab - margen_y, x0_col + margen_x : x1_col - margen_x]
                
                # Para la cabecera usamos PSM 8 (palabra única) que evita ruido
                nro_pieza = _ocr_celda_manuscrita(celda_img, whitelist='0123456789', psm=8)
                piezas_detectadas.append(nro_pieza if nro_pieza else str(c + 1))
        
        piezas = piezas_detectadas if len(piezas_detectadas) == 8 else [str(i) for i in range(1, 9)]
        # Completar a 10 por compatibilidad con el front
        piezas.extend(["", ""])

        # ── 6. COTAS FIJAS (Estructura RP-02) CON INSTRUMENTOS ESTÁTICOS ──────
        COTAS_FIJAS = [
            {"control": "ROSCA 3/8\" BSP", "nominal": "", "tolerancia": "", "instrumento": "ANILLO P-NP"},
            {"control": "INTERIOR Ø12,70", "nominal": "12.70", "tolerancia": "+0,20 -0,0", "instrumento": "PASA"},
            {"control": "PROF(INT Ø12,7) 25,00", "nominal": "25.00", "tolerancia": "+-0,50", "instrumento": "CAD 40"},
            {"control": "PROF(INT Ø11) 29,00", "nominal": "29.00", "tolerancia": "+1,0 -0,0", "instrumento": "CAD 40"},
            {"control": "Alt Parcial 34,00", "nominal": "34.00", "tolerancia": "+-0,1", "instrumento": "CAD 40"},
            {"control": "Alt Total 38,00", "nominal": "38.00", "tolerancia": "+-0,50", "instrumento": "CAD 40"}
        ]

        matrix = []
        
        # Saltamos el renglón de cabecera de piezas (índice 0)
        idx_renglon_datos = 1 

        for idx, cota in enumerate(COTAS_FIJAS):
            cota_dict = cota.copy()
            valores = {str(c + 1): "" for c in range(10)}
            
            try:
                if idx_renglon_datos < len(renglones_y):
                    y0_px, y1_px = renglones_y[idx_renglon_datos]
                    
                    # ── EXTRACCIÓN DE VALORES (OCR) ───
                    margen_y = int((y1_px - y0_px) * 0.12)
                    y0_rec = y0_px + margen_y
                    y1_rec = y1_px - margen_y
                    
                    for c in range(cols):
                        try:
                            x0_col = x_ini_px + c * ancho_col
                            x1_col = x0_col + ancho_col
                            
                            # Aumentar margen X para evitar las líneas divisorias
                            margen_x = int(ancho_col * 0.15)
                            celda_img = img_cv[y0_rec:y1_rec, x0_col + margen_x : x1_col - margen_x]
                            
                            val_ocr = _ocr_celda_manuscrita(celda_img)
                            valores[str(c + 1)] = val_ocr
                        except Exception as cell_err:
                            logger.error(f"[HYBRID] Error OCR celda {c}: {cell_err}")
                            # Deja la celda vacía si falla
                        
                    idx_renglon_datos += 1
            except Exception as row_err:
                logger.error(f"[HYBRID] Error en fila {idx}: {row_err}")
                
            cota_dict["valores"] = valores
            matrix.append(cota_dict)

        logger.info(f"[HYBRID] Finalizado. OP={op}, 6 filas fijas + cabeceras: {piezas[:8]}")

        return {
            "header": {
                "op": op, "proyecto": proyecto, "cliente": cliente,
                "articulo": articulo, "denominacion": denominacion, "operacion": operacion,
            },
            "piezas": piezas,
            "matrix": matrix,
        }

    except Exception as e:
        import traceback
        logger.error(f"[HYBRID] Error: {e}")
        traceback.print_exc()
        vacia["header"]["denominacion"] = "ERROR EN EXTRACCIÓN HÍBRIDA"
        return vacia
