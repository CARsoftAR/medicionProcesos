from rest_framework import serializers
from .models import Control, Tolerancia, PlanillaMedicion, ValorMedicion

class ControlSerializer(serializers.ModelSerializer):
    class Meta:
        model = Control
        fields = ['id', 'nombre', 'pnp']

class ToleranciaSerializer(serializers.ModelSerializer):
    control = ControlSerializer(read_only=True)
    minimo_absoluto = serializers.SerializerMethodField()
    maximo_absoluto = serializers.SerializerMethodField()
    
    class Meta:
        model = Tolerancia
        fields = ['id', 'planilla', 'control', 'minimo', 'nominal', 'maximo', 'posicion', 'minimo_absoluto', 'maximo_absoluto']

    def get_minimo_absoluto(self, obj):
        min_limit, _ = obj.get_absolute_limits()
        return min_limit

    def get_maximo_absoluto(self, obj):
        _, max_limit = obj.get_absolute_limits()
        return max_limit

class ValorMedicionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ValorMedicion
        fields = ['id', 'planilla', 'control', 'tolerancia', 'pieza', 'valor_pieza', 'valor_pnp']
        validators = [] # Disable DRF implicit UniqueTogether validation so custom update_or_create can handle it
        
    def create(self, validated_data):
        request = self.context.get('request')
        # Assign user if available
        operario_id = request.user.id if request and request.user.is_authenticated else None
        
        # Use update_or_create to prevent UniqueConstraint errors for same pieza
        valor, created = ValorMedicion.objects.update_or_create(
            planilla=validated_data.get('planilla'),
            control=validated_data.get('control'),
            pieza=validated_data.get('pieza'),
            defaults={
                'tolerancia': validated_data.get('tolerancia'),
                'valor_pieza': validated_data.get('valor_pieza'),
                'valor_pnp': validated_data.get('valor_pnp'),
                'id_operario': operario_id
            }
        )
        return valor
