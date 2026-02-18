from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
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
    
    path('maestros/clientes/', views.lista_clientes, name='lista_clientes'),
    path('maestros/clientes/nuevo/', views.crear_cliente, name='crear_cliente'),
    path('maestros/clientes/<int:pk>/editar/', views.editar_cliente, name='editar_cliente'),
    path('maestros/clientes/<int:pk>/eliminar/', views.eliminar_cliente, name='eliminar_cliente'),

    path('maestros/elementos/', views.lista_elementos, name='lista_elementos'),
    path('maestros/elementos/nuevo/', views.crear_elemento, name='crear_elemento'),
    path('maestros/elementos/<int:pk>/editar/', views.editar_elemento, name='editar_elemento'),
    path('maestros/elementos/<int:pk>/eliminar/', views.eliminar_elemento, name='eliminar_elemento'),

    path('maestros/instrumentos/', views.lista_instrumentos, name='lista_instrumentos'),
    path('maestros/instrumentos/dashboard/', views.dashboard_calibracion, name='dashboard_calibracion'),
    path('maestros/instrumentos/nuevo/', views.crear_instrumento, name='crear_instrumento'),
    path('maestros/instrumentos/<int:pk>/editar/', views.editar_instrumento, name='editar_instrumento'),
    path('maestros/instrumentos/<int:pk>/eliminar/', views.eliminar_instrumento, name='eliminar_instrumento'),
    path('api/instrumentos/registrar-calibracion/', views.registrar_calibracion_ajax, name='registrar_calibracion_ajax'),
    
    path('perfil/', views.perfil_usuario, name='perfil_usuario'),
    path('usuarios/', views.lista_usuarios, name='lista_usuarios'),
    path('usuarios/nuevo/', views.crear_usuario, name='crear_usuario'),
    path('usuarios/<int:user_id>/editar/', views.editar_usuario, name='editar_usuario'),
    path('usuarios/<int:user_id>/eliminar/', views.eliminar_usuario, name='eliminar_usuario'),
    
    # API
    path('api/create/<str:model_name>/', views.api_create_master, name='api_create_master'),
    path('api/tolerancia/<int:tolerancia_id>/delete/', views.api_delete_tolerancia, name='api_delete_tolerancia'),
    path('api/medicion/guardar/', views.guardar_medicion_ajax, name='guardar_medicion_ajax'),
    path('api/medicion/guardar-maquina/', views.guardar_maquina_ajax, name='guardar_maquina_ajax'),
    path('api/medicion/guardar-instrumento/', views.guardar_instrumento_ajax, name='guardar_instrumento_ajax'),
    path('api/medicion/eliminar-pieza/', views.eliminar_pieza_ajax, name='eliminar_pieza_ajax'),
    path('mediciones/estadisticas/<int:tolerancia_id>/', views.estadisticas_control, name='estadisticas_control'),
    path('panel-geografico/', views.panel_control_geografico, name='panel_control_geografico'),
    path('modo-operario/', views.modo_operario, name='modo_operario'),
    path('operario/', views.operario_medicion, name='operario_medicion'),
    path('api/buscar-op/<str:op>/', views.api_buscar_op_endpoint, name='api_buscar_op_endpoint'),
    path('mediciones/api/operario-data/', views.api_operario_data, name='api_operario_data'),
    path('api/maquina/update-pos/', views.api_update_maquina_pos, name='api_update_maquina_pos'),
    path('mediciones/<int:planilla_id>/exportar-pdf/', views.exportar_pdf, name='exportar_pdf'),
    path('mediciones/<int:planilla_id>/exportar-pdf-pro/', views.exportar_pdf_pro, name='exportar_pdf_pro'),
    path('api/medicion/guardar-observaciones/', views.guardar_observaciones_ajax, name='guardar_observaciones_ajax'),
    path('api/planilla/<int:planilla_id>/delete-full/', views.eliminar_planilla_completa_ajax, name='eliminar_planilla_completa_ajax'),
    
    # Herramientas
    path('herramientas/ocr/', views.ocr_lector_planos, name='ocr_lector_planos'),
    path('api/herramientas/ocr/importar/', views.importar_datos_ocr, name='importar_datos_ocr'),
]


