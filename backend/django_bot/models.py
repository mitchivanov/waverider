from django.db import models
from gridstrat import GridStrategy
import threading
import asyncio

# Create your models here.

class TradingBotManager:
    _instance = None
    _thread = None

    @classmethod
    def start_bot(cls, parameters):
        if cls._instance is None:
            # Initialize the GridStrategy with provided parameters
            cls._instance = GridStrategy(**parameters)
            # Start the strategy in a separate thread
            cls._thread = threading.Thread(target=asyncio.run, args=(cls._instance.execute_strategy(),))
            cls._thread.start()

    @classmethod
    def stop_bot(cls):
        if cls._instance:
            # Stop the strategy execution
            cls._instance.stop()
            cls._instance = None
            cls._thread = None

    @classmethod
    def update_parameters(cls, parameters):
        # Stop the current bot and restart with new parameters
        cls.stop_bot()
        cls.start_bot(parameters)

    @classmethod
    def get_parameters(cls):
        # Return current parameters or default ones
        return {
            'symbol': 'BTCUSDT',
            'asset_a_funds': 1000,
            'asset_b_funds': 0.1,
            'grids': 20,
            'deviation_threshold': 0.02,
            'trail_price': True,
            'only_profitable_trades': False,
        }

    @classmethod
    def get_active_orders(cls):
        # Retrieve active orders from the bot
        if cls._instance:
            return cls._instance.get_active_orders()
        return []

    @classmethod
    def get_trade_history(cls):
        # Retrieve trade history from the bot
        if cls._instance:
            return cls._instance.get_trade_history()
        return []
