import os
import cv2
import time

def ejecutar_calibracion_directa():
    pdf_path = r"C:\Sistemas ABBAMAT\medicionProcesos\media\temporales\RP-02 91327-6 Respaldo  bolilla de cierre.pdf"
    
    if not os.path.exists(pdf_path):
        pdf_path = r"C:\Sistemas ABBAMAT\medicionProcesos\media\RP-02 91327-6 Respaldo  bolilla de cierre.pdf"

    if not os.path.exists(pdf_path):
        print("[ERROR] No se encontro el PDF original en media")
        return

    print("[1/3] Renderizando PDF...")
    img_temp_png = r"C:\Sistemas ABBAMAT\medicionProcesos\temp_render_puro.png"
    try:
        import fitz
        with fitz.open(pdf_path) as pdf_doc:
            page = pdf_doc.load_page(0)
            pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
            pix.save(img_temp_png)
    except Exception as e:
        print("[ERROR] Fallo PyMuPDF: " + str(e))
        return

    img = cv2.imread(img_temp_png)
    if img is None:
        print("[ERROR] OpenCV no pudo cargar la imagen")
        return

    alto, ancho, _ = img.shape
    print("[2/3] Procesando matriz geometrica...")

    # ----------------------------------------------------------------------
    # VALORES DEFINITIVOS CALIBRADOS AL MILIMETRO
    # ----------------------------------------------------------------------
    piezas_maestras = [1, 6, 11, 15, 20, 25, 30, 35, 40, 45, 50]
    fila_inicio_y = 320     
    alto_casillero_y = 53   # Renglones ajustados
    columna_inicio_x = 1032 # Movido a la derecha para no pisar el trazo
    ancho_columna_x = 109   # Ajustado para que no se desplace al final

    for cota_idx in range(1, 11):
        if cota_idx <= 5:
            y_pos = fila_inicio_y + ((cota_idx - 1) * alto_casillero_y)
        else:
            y_pos = 952 + ((cota_idx - 6) * alto_casillero_y)
            
        cv2.line(img, (0, y_pos), (ancho, y_pos), (255, 0, 0), 2)
        cv2.putText(img, "Cota " + str(cota_idx) + " (Y:" + str(y_pos) + ")", (60, y_pos - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
        
        if cota_idx == 5:
            cv2.line(img, (0, y_pos + alto_casillero_y), (ancho, y_pos + alto_casillero_y), (255, 0, 0), 2)
        if cota_idx == 10:
            cv2.line(img, (0, y_pos + alto_casillero_y), (ancho, y_pos + alto_casillero_y), (255, 0, 0), 2)

    for idx, pieza in enumerate(piezas_maestras):
        x_pos = columna_inicio_x + (idx * ancho_columna_x)
        cv2.line(img, (x_pos, 0), (x_pos, alto), (0, 200, 0), 2)
        cv2.putText(img, "Pz " + str(pieza), (x_pos + 12, 180), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 0), 2)
        
        if idx == len(piezas_maestras) - 1:
            cv2.line(img, (x_pos + ancho_columna_x, 0), (x_pos + ancho_columna_x, alto), (0, 200, 0), 2)

    # Creamos un nombre de archivo unico usando la hora actual para romper la cache del disco
    timestamp = time.strftime("%H%M%S")
    nombre_archivo_salida = "GRILLA_CALIBRADA_" + timestamp + ".png"
    ruta_salida = os.path.join(r"C:\Sistemas ABBAMAT\medicionProcesos", nombre_archivo_salida)
    
    cv2.imwrite(ruta_salida, img)

    if os.path.exists(img_temp_png):
        os.remove(img_temp_png)

    print("==========================================================")
    print(" PROCESS SUCCESS!")
    print(" BUSCA Y ABRI ESTE ARCHIVO NUEVO: " + nombre_archivo_salida)
    print("==========================================================")

if __name__ == "__main__":
    ejecutar_calibracion_directa()