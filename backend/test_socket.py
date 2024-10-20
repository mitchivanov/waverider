import asyncio
import logging
from binance import AsyncClient, BinanceSocketManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def test_websocket():
    symbol = 'BTCUSDT'
    try:
        # Initialize the asynchronous Binance client
        async_client = await AsyncClient.create()

        # Initialize the Binance Socket Manager
        bsm = BinanceSocketManager(async_client)

        # Create a WebSocket connection for the symbol ticker
        async with bsm.symbol_ticker_socket(symbol=symbol) as stream:
            logging.info("WebSocket started successfully.")
            while True:
                # Receive a message from the WebSocket
                msg = await stream.recv()
                # Log the current price
                logging.info(f"Current price of {symbol}: {msg['c']}")
                
    except Exception as e:
        logging.error(f"Error occurred: {e}")
    finally:
        # Ensure the client is closed
        await async_client.close_connection()
        logging.info("WebSocket stopped.")

if __name__ == "__main__":
    asyncio.run(test_websocket())
