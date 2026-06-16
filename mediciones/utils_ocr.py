import os
import time
from django.core.management.base import BaseCommand
from django.conf import settings
import cv2

class Command(BaseCommand):
    help = 'Dibuja la grilla de coordenadas calibrada forzando archivo único para evitar caché de Windows'

    def handle(self, *args, **options):
        nombre_archivo = "RP-02 91327-6 Respaldo  bolilla de cierre.pdf"
        pdf_path = os.path.join(settings.MEDIA_ROOT, 'temporales', nombre_archivo)
        
        if not os.path.exists(pdf_path):
            pdf_path = os.path.join(settings.MEDIA_ROOT, nombre_archivo)

        if not os.path.exists(pdf_path):
            self.stdout.write(self.style.ERROR(f"No se encontró el PDF: {pdf_path}"))
            return

        # Generamos un sufijo único usando la hora actual para romper la caché
        timestamp = time.strftime("%H%M%S")
        img_png_path = os.path.join(settings.MEDIA_ROOT, 'temporales', f'base_local_{timestamp}.png')

        try:
            import fitz
            with fitz.open(pdf_path) as pdf_doc:
                page = pdf_doc.load_page(0)
                pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
                pix.save(img_png_path)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error al renderizar: {e}"))
            return

        img = cv2.imread(img_png_path)
        if img is None:
            self.stdout.write(self.style.ERROR("No se pudo cargar la imagen."))
            return

        alto, ancho, _ = img.shape

        # ----------------------------------------------------------------------
        # COORDENADAS REALES AJUSTADAS A LAS LÍNEAS NEGRAS IMPRESAS
        # ----------------------------------------------------------------------
        piezas_maestras = [1, 6, 11, 15, 20, 25, 30, 35, 40, 45, 50]
        
        fila_inicio_y = 320     # Borde superior negro de la primera fila escrita
        alto_casillero_y = 58   # Alto exacto de cada renglón en píxeles
        columna_inicio_x = 990  # Borde izquierdo negro de la columna Pieza 1
        ancho_columna_x = 114   # Ancho exacto de cada columna en píxeles

        # A. DIBUJO DE FILAS ROJAS (Bloque Superior 1-5 e Inferior 6-10 saltando firmas)
        for cota_idx in range(1, 11):
            if cota_idx <= 5:
                y_pos = fila_inicio_y + ((cota_idx - 1) * alto_casillero_y)
            else:
                y_pos = 960 + ((cota_idx - 6) * alto_casillero_y)
                
            cv2.line(img, (0, y_pos), (ancho, y_pos), (0, 0, 255), 2)
            cv2.putText(img, f"Cota {cota_idx} (Y:{y_pos})", (50, y_pos - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            
            if cota_idx == 5:
                cv2.line(img, (0, y_pos + alto_casillero_y), (ancho, y_pos + alto_casillero_y), (0, 0, 255), 2)
            if cota_idx == 10:
                cv2.line(img, (0, y_pos + alto_casillero_y), (ancho, y_pos + alto_casillero_y), (0, 0, 255), 2)

        # B. DIBUJO DE COLUMNAS VERDES
        for idx, pieza in enumerate(piezas_maestras):
            x_pos = columna_inicio_x + (idx * ancho_columna_x)
            cv2.line(img, (x_pos, 0), (x_pos, alto), (0, 255, 0), 2)
            cv2.putText(img, f"Pz {pieza}", (x_pos + 10, 200), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            if idx == len(piezas_maestras) - 1:
                cv2.line(img, (x_pos + ancho_columna_x, 0), (x_pos + ancho_columna_x, alto), (0, 255, 0), 2)

        # 3. Guardamos la imagen final con nombre único en la carpeta temporales
        nombre_salida = f'planilla_calibrada_{timestamp}.png'
        ruta_salida = os.path.join(settings.MEDIA_ROOT, 'temporales', nombre_salida)
        cv2.imwrite(ruta_salida, img)

        # Limpiamos la base temporal
        if os.path.exists(img_png_path):
            os.remove(img_png_path)

        self.stdout.write(self.style.SUCCESS("=================================================================="))
        self.stdout.write(self.style.SUCCESS(" 🔥 ¡MÁQUINA DE CALIBRACIÓN COMPILADA CON NUEVOS PÍXELES!"))
        self.stdout.write(self.style.SUCCESS(f" Abrí el NUEVO archivo generado en: media/temporales/{nombre_salida}"))
        self.stdout.write(self.style.SUCCESS("=================================================================="))