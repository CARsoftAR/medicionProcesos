@echo off
cd /d "c:\Sistemas ABBAMAT\medicionProcesos"
echo Iniciando servidor Django para Medicion de Procesos...
python manage.py runserver 0.0.0.0:8000
pause
