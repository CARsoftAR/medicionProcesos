import os
import base64
from django.core.management.base import BaseCommand
from django.conf import settings
import cv2

class Command(BaseCommand):
    help = 'Dibuja la grilla de coordenadas sobre la planilla de ASPRO para calibrar el recorte'

    def handle(self, *args, **options):
        # 📌 RUTA DE TU PLANILLA DE PRUEBA
        # El script va a buscar el PDF temporal que ya sabemos que tenés en tu carpeta media
        nombre_archivo = "RP-02 91327-6 Respaldo  bolilla de cierre.pdf"
        pdf_path = os.path.join(settings.MEDIA_ROOT, 'temporales', nombre_archivo)
        
        # Fallback si no está el PDF temporal en esa ruta, busca en la raíz de media
        if not os.path.exists(pdf_path):
            pdf_path = os.path.join(settings.MEDIA_ROOT, nombre_archivo)

        if not os.path.exists(pdf_path):
            self.stdout.write(self.style.ERROR(f"No se encontró el PDF en media/ para calibrar. Asegúrate de que exista: {pdf_path}"))
            return

        self.stdout.write(self.style.SUCCESS(f"Leyendo planilla para calibración: {pdf_path}"))

        # 1. Renderizamos el PDF a Imagen con alta resolución (Factor 3x3 = 450 DPI)
        try:
            import fitz  # PyMuPDF
            with fitz.open(pdf_path) as pdf_doc:
                page = pdf_doc.load_page(0)
                pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
                img_data = pix.tobytes("png")
                
                # Guardamos la imagen base nítida en media para procesarla con OpenCV
                img_png_path = os.path.join(settings.MEDIA_ROOT, 'temporales', 'planilla_base_calibrar.png')
                with open(img_png_path, "wb") as f:
                    f.write(img_data)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error al renderizar con PyMuPDF: {e}"))
            return

        # 2. Levantamos la imagen con OpenCV para tirar las líneas guía
        img = cv2.imread(img_png_path)
        if img is None:
            self.stdout.write(self.style.ERROR("No se pudo cargar la imagen procesada con OpenCV."))
            return

        alto, ancho, _ = img.shape
        self.stdout.write(self.style.WARNING(f"Resolución de la imagen de inspección: {ancho}x{alto} píxeles."))

        # ----------------------------------------------------------------------
        # PARÁMETROS DE CALIBRACIÓN GEOMÉTRICA (Ajustables en base a los resultados)
        # ----------------------------------------------------------------------
        # Definimos los saltos estimativos de tus filas de controles y columnas de piezas
        piezas_maestras = [1, 6, 11, 15, 20, 25, 30, 35, 40, 45, 50]
        
        # Coordenadas iniciales estimadas para la grilla Mitutoyo
        fila_inicio_y = 650    # Dónde empieza el primer casillero escrito (Cota 1)
        alto_casillero_y = 95  # Qué tan alto es cada renglón de control
        
        columna_inicio_x = 1020 # Dónde empieza la primera columna de la pieza 1
        ancho_columna_x = 115   # Qué tan ancho es cada casillero de pieza hacia la derecha

        # A. Dibujamos las líneas de las FILAS (Renglones horizontales)
        for cota_idx in range(1, 11): # Probamos dibujar 10 cotas
            y_pos = fila_inicio_y + ((cota_idx - 1) * alto_casillero_y)
            # Dibujamos una línea horizontal roja (Grosor: 2 píxeles)
            cv2.line(img, (0, y_pos), (ancho, y_pos), (0, 0, 255), 2)
            # Metemos un texto indicador al inicio de la fila
            cv2.putText(img, f"Cota {cota_idx} (Y:{y_pos})", (50, y_pos - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        # B. Dibujamos las líneas de las COLUMNAS (Divisiones verticales de las piezas)
        for idx, pieza in enumerate(piezas_maestras):
            x_pos = columna_inicio_x + (idx * ancho_columna_x)
            # Dibujamos una línea vertical verde (Grosor: 2 píxeles)
            cv2.line(img, (x_pos, 0), (x_pos, alto), (0, 255, 0), 2)
            # Metemos el número de la pieza arriba de la línea
            cv2.putText(img, f"Pz {pieza}", (x_pos + 10, 200), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # 3. Guardamos el resultado con la grilla dibujada en tu carpeta media
        ruta_salida = os.path.join(settings.MEDIA_ROOT, 'temporales', 'planilla_calibrada.png')
        cv2.imwrite(ruta_salida, img)

        self.stdout.write(self.style.SUCCESS("=================================================================="))
        self.stdout.write(self.style.SUCCESS(" ¡MÁQUINA DE CALIBRACIÓN COMPLETADA!"))
        self.stdout.write(self.style.SUCCESS(f" Abrí el archivo para revisar las líneas en: media/temporales/planilla_calibrada.png"))
        self.stdout.write(self.style.SUCCESS("=================================================================="))