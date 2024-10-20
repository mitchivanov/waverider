import os
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException, BinanceOrderException

def market_buy_btc(api_key, api_secret, quantity):
    """Perform a market buy order for BTC on Binance Testnet."""
    # Initialize the Binance client for Testnet
    client = Client(api_key, api_secret, testnet=True)
    client.API_URL = 'https://testnet.binance.vision/api'  # Set the Testnet API URL

    try:
        # Execute a market buy order
        order = client.create_order(
            symbol='ETHUSDT',
            side=SIDE_BUY,
            type=ORDER_TYPE_MARKET,
            quantity=quantity
        )
        print(f"Market buy order placed: {order}")
    except BinanceAPIException as e:
        # Handle API exceptions
        print(f"Binance API exception: {e}")
    except BinanceOrderException as e:
        # Handle order exceptions
        print(f"Binance order exception: {e}")
    except Exception as e:
        # Handle any other exceptions
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    # Retrieve API credentials from environment variables
    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_API_SECRET')

    # Define the quantity of BTC to buy
    btc_quantity = 1  # Example quantity

    # Perform the market buy
    market_buy_btc(api_key, api_secret, btc_quantity)
