from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('mediciones/nueva/', views.asignar_op, name='asignar_op'),
    path('mediciones/nueva-op/', views.nueva_medicion_op, name='nueva_medicion_op'),
    path('mediciones/<int:planilla_id>/procesos/', views.crear_procesos, name='crear_procesos'),
    path('mediciones/<int:planilla_id>/tolerancias/', views.asignar_tolerancias, name='asignar_tolerancias'),
    path('mediciones/<int:planilla_id>/ingresar/', views.ingreso_mediciones, name='ingreso_mediciones'),
    path('mediciones/estructuras/', views.lista_estructuras, name='lista_estructuras'),
    path('mediciones/estructuras/eliminar/', views.eliminar_estructura, name='eliminar_estructura'),
    path('mediciones/configurar/', views.configurar_estructura, name='configurar_estructura'),
    
    # Maestros
    path('maestros/procesos/', views.lista_procesos, name='lista_procesos'),
    path('maestros/procesos/nuevo/', views.crear_proceso, name='crear_proceso'),
    path('maestros/procesos/<int:pk>/editar/', views.editar_proceso, name='editar_proceso'),
    path('maestros/procesos/<int:pk>/eliminar/', views.eliminar_proceso, name='eliminar_proceso'),
    
    path('maestros/controles/', views.lista_controles, name='lista_controles'),
    path('maestros/controles/nuevo/', views.crear_control, name='crear_control'),
    path('maestros/controles/<int:pk>/editar/', views.editar_control, name='editar_control'),
    path('maestros/controles/<int:pk>/eliminar/', views.eliminar_control, name='eliminar_control'),
    
    # API
    path('api/create/<str:model_name>/', views.api_create_master, name='api_create_master'),
    path('api/tolerancia/<int:tolerancia_id>/delete/', views.api_delete_tolerancia, name='api_delete_tolerancia'),
    path('api/medicion/guardar/', views.guardar_medicion_ajax, name='guardar_medicion_ajax'),
    path('api/medicion/eliminar-pieza/', views.eliminar_pieza_ajax, name='eliminar_pieza_ajax'),
]
