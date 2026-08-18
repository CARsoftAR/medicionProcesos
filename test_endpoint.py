import os
import django
from django.test import Client

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

client = Client()
response = client.post('/api/calidad/login/', {'legajo': '93', 'pin': '1234'}, content_type='application/json')
print(f"Status: {response.status_code}")
print(f"Response: {response.content.decode()}")
