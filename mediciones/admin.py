from django.contrib import admin
from .models import Articulo, Control, Elemento, Proceso, PlanillaMedicion, Tolerancia, ValorMedicion

@admin.register(Articulo)
class ArticuloAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

@admin.register(Control)
class ControlAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'es_control', 'pnp')
    list_filter = ('es_control', 'pnp')
    search_fields = ('nombre',)

@admin.register(Elemento)
class ElementoAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

@admin.register(Proceso)
class ProcesoAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

class ToleranciaInline(admin.TabularInline):
    model = Tolerancia
    extra = 1

@admin.register(PlanillaMedicion)
class PlanillaMedicionAdmin(admin.ModelAdmin):
    list_display = ('id', 'proyecto', 'num_op', 'articulo', 'proceso', 'elemento', 'cantidad')
    list_filter = ('articulo', 'proceso', 'proyecto')
    search_fields = ('proyecto', 'num_op')
    inlines = [ToleranciaInline]

@admin.register(ValorMedicion)
class ValorMedicionAdmin(admin.ModelAdmin):
    list_display = ('planilla', 'control', 'pieza', 'valor_pieza', 'fecha')
    list_filter = ('planilla', 'control', 'fecha')
