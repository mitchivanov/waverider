import asyncio
from binance import AsyncClient, BinanceSocketManager
import logging
from root import settings  # Ensure this path matches your project structure

# Create a logger
logger = logging.getLogger(__name__)

class BinanceWebSocket:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.async_client = None
        self.bsm = None

    async def start(self):
        """Start a WebSocket connection to receive real-time price updates."""
        try:
            # Initialize the asynchronous Binance client
            self.async_client = await AsyncClient.create()

            # Initialize the Binance Socket Manager
            self.bsm = BinanceSocketManager(self.async_client)

            # Start the WebSocket for the specified symbol
            async with self.bsm.symbol_ticker_socket(symbol=self.symbol) as stream:
                while True:
                    msg = await stream.recv()
                    # Extract and print the price from the message
                    price = msg['c']  # 'c' is the current price in the message
                    print(f"Current price: {price}")

        except Exception as e:
            logger.error(f"Error occurred: {e}")

    async def stop(self):
        """Stop the WebSocket connection."""
        if self.async_client:
            await self.async_client.close_connection()

if __name__ == "__main__":
    symbol = 'BTCUSDT'
    ws_manager = BinanceWebSocket(symbol)

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(ws_manager.start())
    except KeyboardInterrupt:
        print("Stopping WebSocket...")
        loop.run_until_complete(ws_manager.stop())
