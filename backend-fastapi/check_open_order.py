from binance.client import Client

# Replace with your actual Testnet API key and secret
API_KEY = 'YlWpH6a39JrSXKihr51hXXybr9RZEsh7WMsKTxGsRIp1kaslF5Igv6hY6LrHjf9F'
API_SECRET = '4k2hRVjNniNMs6KE9e6Zp8gcg7ds2hDnVh6HFa6lp7L4ir1eFaGEHKjrNZjIj9XY'

# Use the Testnet URL
TESTNET_URL = 'https://testnet.binance.vision/api'

def check_open_orders(symbol):
    # Create a Binance client for Testnet
    client = Client(API_KEY, API_SECRET, testnet=True)

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