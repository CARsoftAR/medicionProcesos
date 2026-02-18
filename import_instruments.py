import os
import django
from datetime import datetime
from dateutil.relativedelta import relativedelta

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from mediciones.models import Instrumento, Cliente

def import_data():
    print("Iniciando importación de instrumentos desde capturas de Excel...")
    
    # 0. Ensure some clients exist for the client instruments
    aspro, _ = Cliente.objects.get_or_create(nombre="ASPRO")
    binning, _ = Cliente.objects.get_or_create(nombre="BINNING")

    instrumentos_data = [
        # --- TAB 1: INSTRUMENTOS DE MEDICION (ABBAMAT) ---
        {
            'nombre': 'CALIBRE DIGITAL', 'codigo': 'CAD 18', 'tipo': 'CALIBRE', 
            'marca': 'SATA', 'rango': '0-200', 'ubicacion': 'MATRICERÍA', 
            'ultima_calibracion': '2025-05-08', 'frecuencia_meses': 12, 'es_propio': True
        },
        {
            'nombre': 'CALIBRE DIGITAL', 'codigo': 'CAD 37', 'tipo': 'CALIBRE', 
            'marca': 'MITUTOYO', 'rango': '0-150', 'ubicacion': 'PRODUCCIÓN', 
            'ultima_calibracion': '2026-01-19', 'frecuencia_meses': 12, 'es_propio': True
        },
        {
            'nombre': 'MICROMETRO', 'codigo': 'MIC 01', 'tipo': 'MICROMETRO', 
            'marca': 'DIGIMESS', 'rango': '75-100', 'ubicacion': 'MATRICERIA', 
            'ultima_calibracion': '2025-02-05', 'frecuencia_meses': 12, 'es_propio': True
        },
        {
            'nombre': 'ALESOMETRO', 'codigo': 'AL006', 'tipo': 'ALESOMETRO', 
            'marca': 'INSIZE', 'rango': '35-60', 'ubicacion': 'PRODUCCIÓN', 'modelo': '2322-60A',
            'ultima_calibracion': '2025-08-29', 'frecuencia_meses': 12, 'es_propio': True
        },
        {
            'nombre': 'STEEL GAUGE BLOCK SET', 'codigo': 'BP1', 'tipo': 'PATRON', 
            'marca': 'ACCUD', 'rango': '1-100', 'serie': '190589', 'ubicacion': 'OFICINA DE PRODUCCIÓN',
            'ultima_calibracion': '2022-04-04', 'frecuencia_meses': 120, 'es_propio': True
        },

        # --- TAB 2: INSTRUMENTOS DE CLIENTES ---
        {
            'nombre': 'CALIBRE CONTROL LUZ Ø 35', 'codigo': 'DC 167', 'tipo': 'CALIBRE', 
            'ubicacion': 'PRODUCCION/ CF', 'cliente': aspro, 'es_propio': False,
            'proxima_calibracion': '2027-01-01', 'frecuencia_meses': 24
        },
        {
            'nombre': 'ANILLO P-NP NEF 1" 1/16 -18 F -3A', 'codigo': 'EQ 04- #23.01', 'tipo': 'PNP', 
            'serie': 'NC 24669 - NC 24670', 'ubicacion': 'PRODUCCION/ CF', 'cliente': binning, 'es_propio': False,
            'ultima_calibracion': '2025-01-08', 'proxima_calibracion': '2028-01-08', 'frecuencia_meses': 36
        },
        {
            'nombre': 'TAPÓN P-NP 1-18 2B', 'codigo': '106620', 'tipo': 'PNP', 
            'serie': 'NC 22554', 'ubicacion': 'OF. PRODUCCIÓN', 'cliente': binning, 'es_propio': False,
            'ultima_calibracion': '2023-10-06', 'proxima_calibracion': '2025-10-06', 'frecuencia_meses': 24
        },

        # --- TAB 3: INSTRUMENTOS OBSOLETOS ---
        {
            'nombre': 'EXTENSIBLE', 'codigo': 'EXT1', 'tipo': 'OTRO', 
            'marca': 'HARTFORD', 'rango': '100.76-100.76', 'ubicacion': 'CALIDAD', 
            'ultima_calibracion': '2024-02-16', 'frecuencia_meses': 12, 'es_propio': True, 
            'es_obsoleto': True, 'en_servicio': False
        }
    ]

    for data in instrumentos_data:
        # Check if already exists to avoid duplicates
        if Instrumento.objects.filter(codigo=data['codigo']).exists():
            print(f"Skipping {data['codigo']} - Ya existe.")
            continue
            
        # Convert date strings to date objects
        if 'ultima_calibracion' in data and data['ultima_calibracion']:
            data['ultima_calibracion'] = datetime.strptime(data['ultima_calibracion'], '%Y-%m-%d').date()
        if 'proxima_calibracion' in data and data['proxima_calibracion']:
            data['proxima_calibracion'] = datetime.strptime(data['proxima_calibracion'], '%Y-%m-%d').date()
            
        Instrumento.objects.create(**data)
        print(f"Importado: {data['codigo']} - {data['nombre']}")

    print("\n--- ¡Importación finalizada con éxito! ---")

if __name__ == "__main__":
    import_data()
