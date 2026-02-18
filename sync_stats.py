import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from mediciones.models import ValorMedicion

def sync_pnp_status():
    print("Sincronizando estados 'OK/NOK' para el Dashboard...")
    
    # Process numeric measurements without status
    query = ValorMedicion.objects.filter(valor_pnp__isnull=True, valor_pieza__isnull=False)
    total = query.count()
    print(f"Encontrados {total} registros numéricos sin estado.")
    
    updated = 0
    for val in query:
        if val.tolerancia:
            min_l, max_l = val.tolerancia.get_absolute_limits()
            if min_l is not None and max_l is not None:
                if min_l <= val.valor_pieza <= max_l:
                    val.valor_pnp = 'OK'
                else:
                    val.valor_pnp = 'NOK'
            else:
                val.valor_pnp = 'OK' # No limits = OK
            val.save()
            updated += 1
            if updated % 100 == 0:
                print(f"Procesados {updated}/{total}...")
    
    # Process PnP measurements where valor_pnp might be something else but needs to be normalized to OK/NOK if applicable
    # (Optional, but let's stick to the main issue)
    
    print(f"Sincronización completada. {updated} registros actualizados.")

if __name__ == '__main__':
    sync_pnp_status()
