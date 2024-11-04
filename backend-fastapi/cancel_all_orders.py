import os
from binance.client import Client
from binance.enums import SIDE_BUY, SIDE_SELL

# Set your API key and secret
API_KEY = 'YlWpH6a39JrSXKihr51hXXybr9RZEsh7WMsKTxGsRIp1kaslF5Igv6hY6LrHjf9F'
API_SECRET = '4k2hRVjNniNMs6KE9e6Zp8gcg7ds2hDnVh6HFa6lp7L4ir1eFaGEHKjrNZjIj9XY'

# Initialize the Binance client for the testnet
client = Client(API_KEY, API_SECRET, testnet=True)

def cancel_all_open_orders():
    try:
        # Fetch all open orders
        open_orders = client.get_open_orders()
        
        if not open_orders:
            print("No open orders to cancel.")
            return

        # Cancel each open order
        for order in open_orders:
            symbol = order['symbol']
            order_id = order['orderId']
            client.cancel_order(symbol=symbol, orderId=order_id)
            print(f"Cancelled order {order_id} for symbol {symbol}")

        print("All open orders have been cancelled.")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    cancel_all_open_orders()