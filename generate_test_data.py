"""
Script para generar 30 piezas de prueba con valores de medición
Ejecutar con: python manage.py shell < generate_test_data.py
O bien: python manage.py runscript generate_test_data (si tienes django-extensions)
"""
import os
import sys
import django
import random
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from mediciones.models import (
    PlanillaMedicion, Tolerancia, ValorMedicion, Control
)

def generate_test_measurements():
    """
    Genera 30 piezas con valores de medición para la planilla existente (OP 46468 / 25-095)
    """
    # Buscar la planilla existente
    try:
        planilla = PlanillaMedicion.objects.get(num_op=46468)
    except PlanillaMedicion.DoesNotExist:
        print("ERROR: No se encontró la planilla con OP 46468")
        print("Planillas disponibles:")
        for p in PlanillaMedicion.objects.all()[:10]:
            print(f"  - ID: {p.id}, OP: {p.num_op}, Proyecto: {p.proyecto}")
        return
    
    print(f"Planilla encontrada: {planilla}")
    
    # Obtener las tolerancias de esta planilla
    tolerancias = Tolerancia.objects.filter(planilla=planilla).select_related('control')
    
    if not tolerancias.exists():
        print("ERROR: No hay tolerancias definidas para esta planilla")
        return
    
    print(f"Tolerancias encontradas: {tolerancias.count()}")
    for t in tolerancias:
        print(f"  - {t.control.nombre}: Nominal={t.nominal}, Min={t.minimo}, Max={t.maximo}")
    
    # Eliminar mediciones existentes para evitar duplicados
    existing_count = ValorMedicion.objects.filter(planilla=planilla).count()
    if existing_count > 0:
        print(f"Eliminando {existing_count} mediciones existentes...")
        ValorMedicion.objects.filter(planilla=planilla).delete()
    
    # Generar valores para 30 piezas
    valores_creados = 0
    
    for pieza_num in range(1, 31):  # Piezas 1 a 30
        for tolerancia in tolerancias:
            # Obtener los límites
            nominal = float(tolerancia.nominal) if tolerancia.nominal else 0
            min_val = float(tolerancia.minimo) if tolerancia.minimo else 0
            max_val = float(tolerancia.maximo) if tolerancia.maximo else 0
            
            # Calcular límites absolutos
            min_limit, max_limit = tolerancia.get_absolute_limits()
            
            if min_limit is None:
                min_limit = nominal - 0.5
            if max_limit is None:
                max_limit = nominal + 0.5
            
            # Generar valor aleatorio
            # 85% dentro de tolerancia, 10% en el límite, 5% fuera
            rand = random.random()
            
            if rand < 0.85:
                # Dentro de tolerancia (zona central)
                rango = max_limit - min_limit
                valor = min_limit + rango * 0.2 + random.random() * rango * 0.6
            elif rand < 0.95:
                # En el límite
                if random.random() < 0.5:
                    valor = min_limit + random.random() * 0.05 * (max_limit - min_limit)
                else:
                    valor = max_limit - random.random() * 0.05 * (max_limit - min_limit)
            else:
                # Fuera de tolerancia
                if random.random() < 0.5:
                    valor = min_limit - random.random() * 0.1 * abs(max_limit - min_limit)
                else:
                    valor = max_limit + random.random() * 0.1 * abs(max_limit - min_limit)
            
            # Redondear a 2 decimales
            valor = round(valor, 2)
            
            # Para controles PnP (pasa/no pasa), generar P o NP
            if tolerancia.control.pnp:
                valor_pnp = 'P' if random.random() < 0.95 else 'NP'
                valor_pieza = None
            else:
                valor_pnp = None
                valor_pieza = valor
            
            # Crear el registro
            ValorMedicion.objects.create(
                planilla=planilla,
                control=tolerancia.control,
                tolerancia=tolerancia,
                pieza=pieza_num,
                valor_pieza=valor_pieza,
                valor_pnp=valor_pnp,
                posicion=tolerancia.posicion,
                op=str(planilla.num_op)
            )
            valores_creados += 1
    
    print(f"\n✅ Generados {valores_creados} valores de medición para 30 piezas")
    print(f"   Planilla: OP {planilla.num_op} / Proyecto {planilla.proyecto}")


if __name__ == '__main__':
    generate_test_measurements()
