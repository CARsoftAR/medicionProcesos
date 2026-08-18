import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token

u = User.objects.get(username='93')
print("Username:", u.username)
print("Check password '93':", u.check_password('93'))
print("Check password '1234':", u.check_password('1234'))
print("Check password '123456':", u.check_password('123456'))
