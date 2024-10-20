from django.urls import path
from .views import TradingParametersView, ActiveOrdersView, TradeHistoryView, home

urlpatterns = [
    path('parameters/', TradingParametersView.as_view(), name='trading_parameters'),
    path('active-orders/', ActiveOrdersView.as_view(), name='active_orders'),
    path('trade-history/', TradeHistoryView.as_view(), name='trade_history'),
    path('', home, name='home'),
]
