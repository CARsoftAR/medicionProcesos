import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from mediciones.models import ValorMedicion, PlanillaMedicion
p = PlanillaMedicion.objects.get(num_op=46468)
print("Valores creados:", ValorMedicion.objects.filter(planilla=p).count())
print("Piezas unicas:", ValorMedicion.objects.filter(planilla=p).values_list("pieza", flat=True).distinct().count())
