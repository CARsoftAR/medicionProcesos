from django.db import models

class Articulo(models.Model):
    nombre = models.CharField(max_length=50)

    class Meta:
        db_table = 'ARTICULOS'
        verbose_name = 'Articulo'
        verbose_name_plural = 'Articulos'

    def __str__(self):
        return self.nombre

class Control(models.Model):
    nombre = models.CharField(max_length=50)
    es_control = models.CharField(max_length=5, default='SI')
    # pnp field suggested by image "AMB Controles"
    pnp = models.BooleanField(default=False, verbose_name="PnP")

    class Meta:
        db_table = 'CONTROLES'
        verbose_name = 'Control'
        verbose_name_plural = 'Controles'

    def __str__(self):
        return self.nombre

class Elemento(models.Model):
    nombre = models.CharField(max_length=100)

    class Meta:
        db_table = 'ELEMENTOS'
        verbose_name = 'Elemento'
        verbose_name_plural = 'Elementos'

    def __str__(self):
        return self.nombre

class Proceso(models.Model):
    # En las pantallas aparece como "Denominaciones" pero el label es "Proceso"
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")

    class Meta:
        db_table = 'PROCESOS'
        verbose_name = 'Proceso'
        verbose_name_plural = 'Procesos'

    def __str__(self):
        return self.nombre

class Cliente(models.Model):
    nombre = models.CharField(max_length=100)

    class Meta:
        db_table = 'CLIENTES'
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'

    def __str__(self):
        return self.nombre

class PlanillaMedicion(models.Model):
    # Hierarchy: Proyecto -> OP -> Articulo -> Proceso -> Elemento
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, db_column='id_cliente')
    proyecto = models.CharField(max_length=50, blank=True, null=True)
    num_op = models.IntegerField(verbose_name='Número OP', blank=True, null=True)
    
    articulo = models.ForeignKey(Articulo, on_delete=models.SET_NULL, null=True, blank=True, db_column='id_articulo')
    proceso = models.ForeignKey(Proceso, on_delete=models.SET_NULL, null=True, db_column='id_proceso')
    elemento = models.ForeignKey(Elemento, on_delete=models.SET_NULL, null=True, db_column='id_elemento')
    
    cantidad = models.FloatField(blank=True, null=True)
    cantidad_realizada = models.FloatField(blank=True, null=True)
    
    id_elaborador = models.IntegerField(blank=True, null=True)
    id_aprobador = models.IntegerField(blank=True, null=True)
    
    fecha_elaborador = models.DateField(blank=True, null=True)
    fecha_aprobador = models.DateField(blank=True, null=True)

    class Meta:
        db_table = 'PLANILLAMEDICION'
        verbose_name = 'Planilla de Medición'
        verbose_name_plural = 'Planillas de Medición'

    def __str__(self):
        return f"Planilla {self.id} - OP {self.num_op}"

class Tolerancia(models.Model):
    planilla = models.ForeignKey(PlanillaMedicion, on_delete=models.CASCADE, db_column='id_planilla')
    control = models.ForeignKey(Control, on_delete=models.CASCADE, db_column='id_control')
    
    minimo = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    nominal = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    maximo = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    
    posicion = models.IntegerField(default=0)
    
    id_instrumento = models.IntegerField(blank=True, null=True)

    def get_absolute_limits(self):
        """
        Returns (min_limit, max_limit) ensuring absolute values are handled correctly.
        Uses same heuristic as nueva_medicion_op view.
        If nominal exists, missing limits default to nominal.
        """
        nominal_f = float(self.nominal) if self.nominal is not None else None
        min_val = float(self.minimo) if self.minimo is not None else None
        max_val = float(self.maximo) if self.maximo is not None else None
        
        min_limit = None
        max_limit = None

        if nominal_f is not None:
            # Heuristic: If val < Nominal/2, assume it's a deviation
            # If val > Nominal/2, assume it's absolute
            
            # Min Logic
            if min_val is not None:
                if abs(min_val) < (abs(nominal_f) / 2.0):
                    min_limit = nominal_f - abs(min_val)
                else:
                    min_limit = min_val
            else:
                min_limit = nominal_f

            # Max Logic
            if max_val is not None:
                if abs(max_val) < (abs(nominal_f) / 2.0):
                    max_limit = nominal_f + abs(max_val)
                else:
                    max_limit = max_val
            else:
                max_limit = nominal_f
        else:
            if min_val is not None: min_limit = min_val
            if max_val is not None: max_limit = max_val
            
        return min_limit, max_limit

    class Meta:
        db_table = 'TOLERANCIAS'
        ordering = ['posicion']
        verbose_name = 'Tolerancia'
        verbose_name_plural = 'Tolerancias'

class ValorMedicion(models.Model):
    planilla = models.ForeignKey(PlanillaMedicion, on_delete=models.CASCADE, db_column='id_planilla')
    control = models.ForeignKey(Control, on_delete=models.CASCADE, db_column='id_control')
    tolerancia = models.ForeignKey(Tolerancia, on_delete=models.SET_NULL, null=True, blank=True, db_column='id_tolerancia')
    
    pieza = models.IntegerField()
    valor_pieza = models.FloatField(blank=True, null=True)
    valor_pnp = models.CharField(max_length=5, blank=True, null=True)
    
    posicion = models.IntegerField(default=0)
    
    id_operario = models.IntegerField(blank=True, null=True)
    id_instrumento = models.IntegerField(blank=True, null=True)
    fecha = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    op = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        db_table = 'VALORMEDICION'
        ordering = ['pieza', 'posicion']
        verbose_name = 'Valor de Medición'
        verbose_name_plural = 'Valores de Medición'
        unique_together = [['planilla', 'control', 'pieza']]
