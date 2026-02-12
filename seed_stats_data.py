import os
import django
import random

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from mediciones.models import ValorMedicion, Tolerancia

def generate_data():
    # 1. Ø INTERIOR (ID 64) -> EXCELENTE (CPK > 2.0)
    # Nominal 50.60, LSL 50.50, USL 50.70
    t64 = Tolerancia.objects.get(id=64)
    val64 = ValorMedicion.objects.filter(tolerancia=t64).order_by('pieza')
    for v in val64:
        # Very tight variation around nominal
        v.valor_pieza = round(50.60 + random.uniform(-0.01, 0.01), 3)
        v.save()
    print("Updated ID 64 (Ø INTERIOR) to EXCELENTE")

    # 2. ALTURA TOTAL (ID 60) -> ACEPTABLE (CPK ~1.5)
    # Nominal 60.50, LSL 60.50, USL 61.00
    # Range is 0.50. 
    t60 = Tolerancia.objects.get(id=60)
    val60 = ValorMedicion.objects.filter(tolerancia=t60).order_by('pieza')
    for v in val60:
        # Centered but with more breathing room
        v.valor_pieza = round(60.75 + random.uniform(-0.05, 0.05), 3)
        v.save()
    print("Updated ID 60 (ALTURA TOTAL) to ACEPTABLE")

if __name__ == "__main__":
    generate_data()
