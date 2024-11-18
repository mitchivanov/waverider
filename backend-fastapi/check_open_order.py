from binance.client import Client

# Replace with your actual Testnet API key and secret
api_key = 'R1iPxmWzKPragpC2XspJITGIL3wmKqDPY8znltkOLyB7c8I4xyY6LnQI7ZVR5Qd2'
api_secret = 'Ry4TT8syAN50NBURYsUY13cFZJ5r6NZJNAp5xkFKdFSr3uKMudxhCvlTP4eJZwCi'

# Use the Testnet URL
TESTNET_URL = 'https://testnet.binance.vision/api'

def check_open_orders(symbol):
    # Create a Binance client for Testnet
    client = Client(api_key, api_secret, testnet=True)

    try:
        # Get open orders for the specified symbol
        open_orders = client.get_open_orders(symbol=symbol)
        return open_orders
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return []

def main():
    symbol = 'BTCUSDT'  # Change this to your desired trading pair
    open_orders = check_open_orders(symbol)

    if open_orders:
        print(f"Number of open orders for {symbol}: {len(open_orders)}")
        for order in open_orders:
            print(f"Order ID: {order['orderId']}, Price: {order['price']}, Quantity: {order['origQty']}")
    else:
        print(f"No open orders for {symbol}.")

if __name__ == "__main__":
    main()