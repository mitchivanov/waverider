import os
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException

def cancel_all_orders(api_key, api_secret):
    """Cancel all outstanding orders on Binance."""
    # Initialize the Binance client
    client = Client(api_key, api_secret, testnet=True)
    client.API_URL = 'https://testnet.binance.vision/api'  # Set the Testnet API URL

    try:
        # Fetch all open orders
        open_orders = client.get_open_orders()
        print(f"Found {len(open_orders)} open orders.")

        # Cancel each open order
        for order in open_orders:
            try:
                result = client.cancel_order(
                    symbol=order['symbol'],
                    orderId=order['orderId']
                )
                print(f"Cancelled order {order['orderId']} for {order['symbol']}: {result}")
            except BinanceAPIException as e:
                print(f"Failed to cancel order {order['orderId']} for {order['symbol']}: {e}")
            except BinanceOrderException as e:
                print(f"Order exception for {order['orderId']} for {order['symbol']}: {e}")
            except Exception as e:
                print(f"An error occurred while cancelling order {order['orderId']}: {e}")

    except BinanceAPIException as e:
        print(f"Binance API exception: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    # Retrieve API credentials from environment variables
    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_API_SECRET')

    # Cancel all outstanding orders
    cancel_all_orders(api_key, api_secret)

