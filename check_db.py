import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
print("=== USUARIOS ===")
for u in User.objects.all():
    operario = getattr(u, 'operario', None)
    op_activo = operario.activo if operario else 'No es operario'
    print(f"Username (Legajo): {u.username} | is_active: {u.is_active} | Operario Activo: {op_activo} | Password: {u.password[:20]}...")
