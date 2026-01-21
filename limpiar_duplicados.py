"""
Script para eliminar registros duplicados de ValorMedicion.
Mantiene solo el registro más reciente de cada combinación (planilla, control, pieza).
"""

from mediciones.models import ValorMedicion
from django.db.models import Count

# Encontrar duplicados
duplicates = ValorMedicion.objects.values('planilla', 'control', 'pieza').annotate(
    count=Count('id')
).filter(count__gt=1)

print(f"Encontrados {duplicates.count()} grupos de duplicados")

deleted_count = 0

for dup in duplicates:
    # Obtener todos los registros duplicados
    records = ValorMedicion.objects.filter(
        planilla_id=dup['planilla'],
        control_id=dup['control'],
        pieza=dup['pieza']
    ).order_by('-fecha')  # Ordenar por fecha descendente
    
    # Mantener el más reciente (primero), eliminar el resto
    to_keep = records.first()
    to_delete = records.exclude(id=to_keep.id)
    
    count = to_delete.count()
    print(f"Planilla {dup['planilla']}, Control {dup['control']}, Pieza {dup['pieza']}: "
          f"Manteniendo ID {to_keep.id}, eliminando {count} duplicado(s)")
    
    to_delete.delete()
    deleted_count += count

print(f"\nTotal de registros duplicados eliminados: {deleted_count}")
