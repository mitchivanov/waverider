from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException
from root import settings
import aiohttp

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

    async def place_order_async(self, symbol: str, side: str, quantity: float, price: float, order_type: str = 'LIMIT'):
        """Place an order on Binance asynchronously."""
        async with aiohttp.ClientSession() as session:
            try:
                # Example API call to place an order
                url = "https://api.binance.com/api/v3/order"
                params = {
                    "symbol": symbol,
                    "side": side,
                    "type": order_type,
                    "quantity": quantity,
                    "price": price,
                    # Add other necessary parameters
                }
                async with session.post(url, params=params) as response:
                    return await response.json()
            except (BinanceAPIException, BinanceRequestException) as e:
                print(f"An error occurred while placing an order: {str(e)}")
                return None

    async def get_current_price_async(self, symbol: str) -> float:
        """Fetch the current price for a given trading pair asynchronously."""
        async with aiohttp.ClientSession() as session:
            try:
                url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
                async with session.get(url) as response:
                    data = await response.json()
                    return float(data['price'])
            except (BinanceAPIException, BinanceRequestException) as e:
                print(f"An error occurred while fetching the current price from Binance: {str(e)}")
                return None
