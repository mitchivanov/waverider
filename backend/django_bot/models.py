from django.db import models
from gridstrat import GridStrategy
import threading
import asyncio
import logging

# Create your models here.

class TradingBotManager:
    _instance = None
    _thread = None

    @classmethod
    def start_bot(cls, parameters):
        if cls._instance is None:
            try:
                # Initialize the GridStrategy with provided parameters
                cls._instance = GridStrategy(**parameters)
                # Start the strategy in a separate thread
                cls._thread = threading.Thread(target=cls._run_strategy)
                cls._thread.start()
                logging.info("Trading bot started successfully.")
            except Exception as e:
                logging.error(f"Error starting trading bot: {str(e)}")
                cls._instance = None
                cls._thread = None
                raise

    @classmethod
    def stop_bot(cls):
        if cls._instance:
            logging.info("Stopping the trading bot...")
            cls._instance.stop()
            if cls._thread:
                cls._thread.join(timeout=10)  # Wait for the thread to finish
                if cls._thread.is_alive():
                    logging.warning("Bot thread did not stop gracefully.")
            cls._instance = None
            cls._thread = None
            logging.info("Trading bot stopped.")

    @classmethod
    def update_parameters(cls, parameters):
        try:
            logging.info("Updating trading bot parameters...")
            cls.stop_bot()
            cls.start_bot(parameters)
            logging.info("Trading bot parameters updated successfully.")
        except Exception as e:
            logging.error(f"Error updating trading bot parameters: {str(e)}")
            raise

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
        if cls._instance and cls.is_bot_running():
            try:
                return cls._instance.get_active_orders()
            except Exception as e:
                logging.error(f"Error getting active orders: {str(e)}")
                return {"error": "Failed to retrieve active orders"}
        return {"error": "Bot not running"}

    @classmethod
    def get_trade_history(cls):
        if cls._instance and cls.is_bot_running():
            try:
                return cls._instance.get_trade_history()
            except Exception as e:
                logging.error(f"Error getting trade history: {str(e)}")
                return {"error": "Failed to retrieve trade history"}
        return {"error": "Bot not running"}

    @classmethod
    def _run_strategy(cls):
        try:
            asyncio.run(cls._instance.execute_strategy())
        except Exception as e:
            logging.error(f"Error in strategy execution: {str(e)}")

    @classmethod
    def is_bot_running(cls):
        return cls._instance is not None and cls._thread is not None and cls._thread.is_alive()
