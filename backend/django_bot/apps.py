from django.apps import AppConfig


class DjangoBotConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'django_bot'  # Updated app name

    def ready(self):
        from .models import TradingBotManager
        # Define default parameters
        parameters = {
            'symbol': 'ETHUSDT',
            'asset_a_funds': 1000,
            'asset_b_funds': 0.5,
            'grids': 10,
            'deviation_threshold': 0.02,
            'growth_factor': 0.5,
            'use_granular_distribution': True,
            'trail_price': True,
            'only_profitable_trades': False,
        }
        # Start the bot with default parameters
        TradingBotManager.start_bot(parameters)
