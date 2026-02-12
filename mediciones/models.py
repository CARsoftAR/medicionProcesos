from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Profile(models.Model):
    ROLE_CHOICES = [
        ('OPERADOR', 'Operador (Carga de Datos)'),
        ('CALIDAD', 'Supervisor / Calidad (Control Total)'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='OPERADOR')

    class Meta:
        db_table = 'USER_PROFILES'
        verbose_name = 'Perfil de Usuario'
        verbose_name_plural = 'Perfiles de Usuarios'

    def __str__(self):
        return f"{self.user.username} - {self.role}"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.profile.save()
    except Profile.DoesNotExist:
        Profile.objects.create(user=instance)


class Maquina(models.Model):
    nombre = models.CharField(max_length=100)
    codigo = models.CharField(max_length=50, blank=True, null=True, verbose_name="Código/Interno")
    descripcion = models.TextField(blank=True, null=True)
    x_pos = models.FloatField(blank=True, null=True, verbose_name="Posición X (%)")
    y_pos = models.FloatField(blank=True, null=True, verbose_name="Posición Y (%)")


    class Meta:
        db_table = 'MAQUINAS'
        verbose_name = 'Máquina'
        verbose_name_plural = 'Máquinas'

    def __str__(self):
        return f"{self.nombre} ({self.codigo})" if self.codigo else self.nombre

class Instrumento(models.Model):
    TIPO_CHOICES = [
        ('CALIBRE', 'Calibre'),
        ('MICROMETRO', 'Micrómetro'),
        ('COMPARADOR', 'Comparador'),
        ('GALGA', 'Galga'),
        ('OTRO', 'Otro'),
    ]
    nombre = models.CharField(max_length=100)
    codigo = models.CharField(max_length=50, blank=True, null=True, verbose_name="Código/Inventario")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='CALIBRE')
    marca = models.CharField(max_length=50, blank=True, null=True)
    ultima_calibracion = models.DateField(blank=True, null=True, verbose_name="Última Calibración")
    frecuencia_meses = models.IntegerField(default=12, verbose_name="Frecuencia (Meses)")
    proxima_calibracion = models.DateField(blank=True, null=True, verbose_name="Próxima Calibración")
    alerta_dias = models.IntegerField(default=15, verbose_name="Alerta Anticipada (Días)")
    certificado_nro = models.CharField(max_length=100, blank=True, null=True, verbose_name="Nro. Certificado")
    en_servicio = models.BooleanField(default=True, verbose_name="En Servicio")

    class Meta:
        db_table = 'INSTRUMENTOS'
        verbose_name = 'Instrumento'
        verbose_name_plural = 'Instrumentos'

    def is_calibracion_vencida(self):
        from datetime import date
        if not self.proxima_calibracion:
            return False
        return date.today() > self.proxima_calibracion

    def is_en_alerta(self):
        from datetime import date, timedelta
        if not self.proxima_calibracion:
            return False
        dias_restantes = (self.proxima_calibracion - date.today()).days
        return 0 <= dias_restantes <= self.alerta_dias

    def __str__(self):
        return f"{self.nombre} ({self.codigo})" if self.codigo else self.nombre

    def save(self, *args, **kwargs):
        # Auto-calculate next calibration date if not manually set
        if self.ultima_calibracion and not self.proxima_calibracion:
            from dateutil.relativedelta import relativedelta
            self.proxima_calibracion = self.ultima_calibracion + relativedelta(months=self.frecuencia_meses)
        super().save(*args, **kwargs)

class HistorialCalibracion(models.Model):
    instrumento = models.ForeignKey(Instrumento, on_delete=models.CASCADE, related_name='historial')
    fecha_calibracion = models.DateField()
    resultado = models.CharField(max_length=20, choices=[('APROBADO', 'Aprobado'), ('RECHAZADO', 'Rechazado')], default='APROBADO')
    certificado_nro = models.CharField(max_length=100, blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        db_table = 'INSTRUMENTO_CALIBRACIONES'
        verbose_name = 'Historial de Calibración'
        verbose_name_plural = 'Historial de Calibraciones'
        ordering = ['-fecha_calibracion']

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
    maquina = models.ForeignKey(Maquina, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Máquina", db_column='id_maquina')
    
    cantidad = models.FloatField(blank=True, null=True)
    cantidad_realizada = models.FloatField(blank=True, null=True)
    
    id_elaborador = models.IntegerField(blank=True, null=True)
    id_aprobador = models.IntegerField(blank=True, null=True)
    aprobador = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='planillas_aprobadas', db_column='fk_aprobador')
    observaciones = models.TextField(blank=True, null=True)
    
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
    
    minimo = models.DecimalField(max_digits=12, decimal_places=4, blank=True, null=True)
    nominal = models.DecimalField(max_digits=12, decimal_places=4, blank=True, null=True)
    maximo = models.DecimalField(max_digits=12, decimal_places=4, blank=True, null=True)
    
    posicion = models.IntegerField(default=0)
    
    id_instrumento = models.IntegerField(blank=True, null=True)
    instrumento = models.ForeignKey(Instrumento, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Instrumento", db_column='fk_instrumento')

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
