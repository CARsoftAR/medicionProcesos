from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from django.shortcuts import get_object_or_404

from .models import PlanillaMedicion, Tolerancia, ValorMedicion, Control, Proceso, Articulo, Elemento, Maquina, HistorialCalibracion, Instrumento
from .serializers import ToleranciaSerializer, ValorMedicionSerializer
from django.db import transaction
from django.conf import settings


class CotasPlanillaAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, op_num, format=None):
        """
        Retorna las cotas (Tolerancias y Controles) a medir para una Orden de Proceso.
        """
        planilla = get_object_or_404(PlanillaMedicion, num_op=op_num)
        tolerancias = Tolerancia.objects.filter(planilla=planilla).select_related('control').order_by('posicion')
        serializer = ToleranciaSerializer(tolerancias, many=True)
        
        # Obtener lista de piezas ya registradas (sin repetidos, ordenadas)
        valores = ValorMedicion.objects.filter(planilla=planilla)
        piezas = valores.values_list('pieza', flat=True).distinct().order_by('pieza')
        piezas_registradas = list(piezas)
        
        # Agrupar los valores por pieza
        mediciones_valores = {}
        for val in valores:
            p = str(val.pieza)
            if p not in mediciones_valores:
                mediciones_valores[p] = {}
            if val.tolerancia_id:
                if val.valor_pieza is not None:
                    v = val.valor_pieza
                    # Remove trailing .0 if it's an integer to preserve exactness visually
                    val_str = str(int(v)) if v.is_integer() else str(v)
                    mediciones_valores[p][val.tolerancia_id] = val_str
                else:
                    mediciones_valores[p][val.tolerancia_id] = ''
        
        return Response({
            'planilla_id': planilla.id,
            'op_num': planilla.num_op,
            'proyecto': planilla.proyecto,
            'cliente': planilla.cliente.nombre if planilla.cliente else None,
            'cotas': serializer.data,
            'piezas_registradas': piezas_registradas,
            'mediciones_valores': mediciones_valores
        }, status=status.HTTP_200_OK)

class GuardarMedicionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, format=None):
        """
        Guarda una nueva medicin enviada desde la App Mvil, 
        quedando vinculada al request.user mediante TokenAuth.
        """
        is_many = isinstance(request.data, list)
        serializer = ValorMedicionSerializer(data=request.data, context={'request': request}, many=is_many)
        if serializer.is_valid():
            serializer.save()
            return Response({'status': 'success', 'data': serializer.data}, status=status.HTTP_201_CREATED)
        return Response({'status': 'error', 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

class BorrarPiezaAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, op_num, pieza, format=None):
        planilla = get_object_or_404(PlanillaMedicion, num_op=op_num)
        deleted, _ = ValorMedicion.objects.filter(planilla=planilla, pieza=pieza).delete()
        if deleted > 0:
            return Response({'status': 'success', 'deleted': deleted}, status=status.HTTP_200_OK)
        return Response({'status': 'error', 'message': 'Pieza no encontrada'}, status=status.HTTP_404_NOT_FOUND)

class OperarioLoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, format=None):
        legajo = request.data.get('legajo')
        pin = request.data.get('pin')
        
        if not legajo or not pin:
            return Response({'error': 'Legajo y PIN son requeridos'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(username=legajo)
        except User.DoesNotExist:
            return Response({'error': 'Legajo incorrecto'}, status=status.HTTP_404_NOT_FOUND)

        if not user.check_password(pin):
            return Response({'error': 'PIN incorrecto'}, status=status.HTTP_401_UNAUTHORIZED)
            
        if hasattr(user, 'operario') and not user.operario.activo:
            return Response({'error': 'Operario inactivo'}, status=status.HTTP_403_FORBIDDEN)
            
        token, _ = Token.objects.get_or_create(user=user)
        return Response({'token': token.key}, status=status.HTTP_200_OK)
