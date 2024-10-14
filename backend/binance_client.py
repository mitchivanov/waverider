from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException
from root import settings

class BinanceClient:
    def __init__(self):
        # Initialize the Binance client with API keys
        self.client = Client(
            api_key=settings.BINANCE_API_KEY,
            api_secret=settings.BINANCE_API_SECRET,
            testnet=True  # Use Binance Testnet
        )

    def get_current_price(self, symbol: str) -> float:
        """Fetch the current price for a given trading pair."""
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except (BinanceAPIException, BinanceRequestException) as e:
            print(f"An error occurred while fetching the current price from Binance: {str(e)}")
            print(f"Error type: {type(e).__name__}")
            print(f"Error code: {getattr(e, 'code', 'N/A')}")
            print(f"Error message: {getattr(e, 'message', str(e))}")
            return None

    def place_order(self, symbol: str, side: str, quantity: float, order_type: str = 'MARKET'):
        """Place an order on Binance."""
        try:
            order = self.client.create_order(
                symbol=symbol,
                side=side,
                type=order_type,
                quantity=quantity
            )
            return order
        except (BinanceAPIException, BinanceRequestException) as e:
            print(f"An error occurred while placing an order: {str(e)}")
            return None
