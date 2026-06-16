import cv2
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

img = cv2.imread('celda_prueba.png')
if img is not None:
    # 1. Pasamos a gris
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 2. APLICAMOS BLUR (Quita el ruido de los píxeles de la birome)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # 3. ADAPTIVE THRESHOLD (Esto es clave: se adapta si hay zonas oscuras/claras)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    
    # Leer
    texto = pytesseract.image_to_string(thresh, config='--psm 7 -c tessedit_char_whitelist=0123456789.,')
    print(f"Detectado: {texto}")
    
    # Debug: Guardá esta imagen para ver qué es lo que realmente está viendo Tesseract
    cv2.imwrite('debug_vision.png', thresh)
    print("Imagen de prueba guardada como 'debug_vision.png'. Abrila para ver si el número se ve negro y el fondo blanco.")