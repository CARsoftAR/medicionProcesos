import os
import cv2
import fitz
import numpy as np
import json

def extraer_coordenadas_planilla(pdf_path):
    """
    Procesa el PDF cargado y devuelve la matriz exacta de coordenadas 
    de los 100 casilleros para usar en la interfaz de carga manual.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError("El archivo PDF no existe.")

    # 1. Renderizar el PDF a alta resolución para no perder calidad
    doc = fitz.open(pdf_path)
    page = doc.load_page(0)
    pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
    
    # Convertir el renderizado directo a formato OpenCV sin guardar en disco
    img_data = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.h, pix.w, 3))
    img = cv2.cvtColor(img_data, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)[1]

    # 2. Aislar líneas completas (morfología)
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (50, 1))
    horiz = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_h)

    kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 50))
    vert = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_v)

    # Helper para agrupar píxeles de una misma línea impresa (grosor)
    def procesar_eje(img_lineas, eje_proyeccion, limite_largo):
        sumas = np.sum(img_lineas, axis=eje_proyeccion)
        picos = np.where(sumas > limite_largo * 255)[0]
        
        coordenadas = []
        if len(picos) == 0: return coordenadas

        cluster = [picos[0]]
        for p in picos[1:]:
            if p - cluster[-1] < 15:
                cluster.append(p)
            else:
                coordenadas.append(int(np.mean(cluster)))
                cluster = [p]
        coordenadas.append(int(np.mean(cluster)))
        return coordenadas

    # 3. Detectar todas las coordenadas de tinta reales
    coordenadas_x = procesar_eje(vert, eje_proyeccion=0, limite_largo=100)
    coordenadas_y = procesar_eje(horiz, eje_proyeccion=1, limite_largo=200)

    # 4. Filtrar geolocalización de la tabla de medición
    x_columnas = sorted([x for x in coordenadas_x if x > 900])[:11]
    y_bloque_1 = sorted([y for y in coordenadas_y if 300 < y < 700])
    y_bloque_2 = sorted([y for y in coordenadas_y if 900 < y < 1400])

    if len(x_columnas) < 11 or not y_bloque_1 or not y_bloque_2:
        raise ValueError("No se pudo detectar la estructura de la tabla RP-02 en el documento.")

    # 5. GEOMETRÍA INDESTRUCTIBLE:
    y_top_1, y_bottom_1 = y_bloque_1[0], y_bloque_1[-1]
    alto_fila_1 = (y_bottom_1 - y_top_1) / 5

    y_top_2, y_bottom_2 = y_bloque_2[0], y_bloque_2[-1]
    alto_fila_2 = (y_bottom_2 - y_top_2) / 5

    matriz_casilleros = []

    # Construir Bloque 1 (Cotas 1 a 5)
    for fila in range(5):
        y_actual = int(y_top_1 + (fila * alto_fila_1))
        h_actual = int(alto_fila_1)
        for col in range(10):
            x_actual = x_columnas[col]
            w_actual = x_columnas[col+1] - x_actual
            matriz_casilleros.append({
                "bloque": 1, "fila": fila + 1, "columna": col + 1,
                "x": x_actual, "y": y_actual, "w": w_actual, "h": h_actual
            })

    # Construir Bloque 2 (Cotas 6 a 10)
    for fila in range(5):
        y_actual = int(y_top_2 + (fila * alto_fila_2))
        h_actual = int(alto_fila_2)
        for col in range(10):
            x_actual = x_columnas[col]
            w_actual = x_columnas[col+1] - x_actual
            matriz_casilleros.append({
                "bloque": 2, "fila": fila + 6, "columna": col + 1,
                "x": x_actual, "y": y_actual, "w": w_actual, "h": h_actual
            })

    return matriz_casilleros


if __name__ == "__main__":
    # Ruta de tu PDF de prueba
    pdf = r"C:\Sistemas ABBAMAT\medicionProcesos\media\temporales\RP-02 91327-6 Respaldo  bolilla de cierre.pdf"
    
    print("Probando el motor logico de deteccion...")
    try:
        resultado = extraer_coordenadas_planilla(pdf)
        print("\n==================================================")
        print(f" ¡EXITO! Se calcularon {len(resultado)} casilleros.")
        print("==================================================")
        
        print("\nMuestra de la estructura JSON generada:")
        print(json.dumps(resultado[:2], indent=4))
        
    except Exception as e:
        print(f"\n[ERROR] El proceso fallo: {e}")