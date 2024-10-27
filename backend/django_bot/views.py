from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import TradingParametersSerializer
from .models import TradingBotManager
from django.http import HttpResponse
import logging

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
        try:
            orders = TradingBotManager.get_active_orders()
            logging.info(f"Retrieved {len(orders)} active orders.")
            return Response(orders)
        except Exception as e:
            logging.error(f"Error retrieving active orders: {str(e)}")
            return Response({"error": "Failed to retrieve active orders"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class TradeHistoryView(APIView):
    def get(self, request):
        try:
            history = TradingBotManager.get_trade_history()
            logging.info(f"Retrieved trade history with {len(history)} entries.")
            return Response(history)
        except Exception as e:
            logging.error(f"Error retrieving trade history: {str(e)}")
            return Response({"error": "Failed to retrieve trade history"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class BotStatusView(APIView):
    def get(self, request):
        is_running = TradingBotManager.is_bot_running()
        return Response({"is_running": is_running})

def home(request):
    return HttpResponse("Welcome to the Django Bot!")
