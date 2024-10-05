# Import the necessary module from the python-binance library
from binance.client import Client

# Initialize the Binance client
# You can use an API key and secret if you have one, but it's not necessary for public data
client = Client()

# Fetch the current price of BTC/USDT
btc_price = client.get_symbol_ticker(symbol="BTCUSDT")

# Print the current price
print(f"Current BTC Price: {btc_price['price']}")