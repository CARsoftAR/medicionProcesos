import os
import cv2
import time

def ejecutar_calibracion_directa():
    pdf_path = r"C:\Sistemas ABBAMAT\medicionProcesos\media\temporales\RP-02 91327-6 Respaldo  bolilla de cierre.pdf"
    
    if not os.path.exists(pdf_path):
        pdf_path = r"C:\Sistemas ABBAMAT\medicionProcesos\media\RP-02 91327-6 Respaldo  bolilla de cierre.pdf"

    if not os.path.exists(pdf_path):
        print("[ERROR] No se encontro el PDF")
        return

    print("[1/3] Renderizando PDF...")
    img_temp_png = r"C:\Sistemas ABBAMAT\medicionProcesos\temp_render_puro.png"
    try:
        import fitz
        with fitz.open(pdf_path) as d:
            p = d.load_page(0)
            pix = p.get_pixmap(matrix=fitz.Matrix(3,3))
            pix.save(img_temp_png)
    except Exception as e:
        print("[ERROR] PyMuPDF: " + str(e))
        return

    img = cv2.imread(img_temp_png)
    if img is None:
        print("[ERROR] OpenCV no cargo imagen")
        return

    alto, ancho, _ = img.shape
    print("[2/3] Procesando matriz...")
    piezas = [1, 6, 11, 15, 20, 25, 30, 35, 40, 45, 50]

    # 📐 NUEVAS COORDENADAS DEFINITIVAS DE CALIBRACIÓN
    for c in range(1, 11):
        y = 380 + ((c-1)*62) if c <= 5 else 1010 + ((c-6)*62)
        cv2.line(img, (0, y), (ancho, y), (255, 0, 0), 2)
        cv2.putText(img, "Cota " + str(c) + " (Y:" + str(y) + ")", (60, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
        if c == 5: cv2.line(img, (0, y+62), (ancho, y+62), (255, 0, 0), 2)
        if c == 10: cv2.line(img, (0, y+62), (ancho, y+62), (255, 0, 0), 2)

    for i, pz in enumerate(piezas):
        x = 1092 + (i * 111)
        cv2.line(img, (x, 0), (x, alto), (0, 200, 0), 2)
        cv2.putText(img, "Pz " + str(pz), (x + 12, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 0), 2)
        if i == len(piezas) - 1: cv2.line(img, (x + 111, 0), (x + 111, alto), (0, 200, 0), 2)

    ts = time.strftime("%H%M%S")
    out = os.path.join(r"C:\Sistemas ABBAMAT\medicionProcesos", "GRILLA_CALIBRADA_" + ts + ".png")
    cv2.imwrite(out, img)
    
    if os.path.exists(img_temp_png):
        os.remove(img_temp_png)
        
    print("==================================================")
    print(" ARCHIVO GENERADO EXITO: GRILLA_CALIBRADA_" + ts + ".png")
    print("==================================================")

if __name__ == "__main__":
    ejecutar_calibracion_directa()        cv2.line(img, (x, 0), (x, alto), (0, 200, 0), 2)
