import os
from binance.client import Client
from binance.enums import SIDE_BUY, SIDE_SELL


# Set your API key and secret
api_key = '55euYhdLmx17qhTB1KhBSbrsS3A79bYU0C408VHMYsTTMcsyfSMboJ1d1uEWNLq3'
api_secret = '2zlWvVVQIrj5ZryMNCkt9KIqowlQQMdG0bcV4g4LAinOnF8lc7O3Udumn6rIAyLb'

# Initialize the Binance client for the testnet
client = Client(api_key, api_secret, testnet=True)

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

        print("Number of open orders cancelled: ", len(open_orders))

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    cancel_all_open_orders()