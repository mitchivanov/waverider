from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import TradingParametersSerializer
from .models import TradingBotManager
from django.http import HttpResponse

class TradingParametersView(APIView):
    def get(self, request):
        # Get current trading parameters
        parameters = TradingBotManager.get_parameters()
        serializer = TradingParametersSerializer(parameters)
        return Response(serializer.data)

    def post(self, request):
        # Update trading parameters
        serializer = TradingParametersSerializer(data=request.data)
        if serializer.is_valid():
            TradingBotManager.update_parameters(serializer.validated_data)
            return Response({'status': 'Parameters updated'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ActiveOrdersView(APIView):
    def get(self, request):
        orders = TradingBotManager.get_active_orders()
        return Response(orders)

class TradeHistoryView(APIView):
    def get(self, request):
        history = TradingBotManager.get_trade_history()
        return Response(history)

def home(request):
    return HttpResponse("Welcome to the Django Bot!")
