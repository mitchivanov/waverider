from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException
import asyncio
import hmac
import hashlib
import time
import aiohttp
import logging
from aiohttp import TCPConnector
from asyncio import Semaphore

class BinanceClient:
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        
        # Configure connection pooling and timeouts
        connector = TCPConnector(
            limit=100,  # Maximum number of concurrent connections
            ttl_dns_cache=300,  # DNS cache TTL in seconds
            force_close=False,  # Keep connections alive
            enable_cleanup_closed=True  # Clean up closed connections
        )
        
        # Configure client timeout
        timeout = aiohttp.ClientTimeout(
            total=10,  # Total timeout in seconds
            connect=2,  # Connection timeout
            sock_read=5  # Socket read timeout
        )
        
        # Initialize session with optimized settings
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={'X-MBX-APIKEY': self.api_key}
        )
        
        # Rate limiting semaphore (adjust the number based on your API limits)
        self.order_semaphore = Semaphore(10)  # Allow 10 concurrent order operations
        
        # Set the base URL based on the testnet parameter
        if self.testnet:
            self.BASE_URL = 'https://testnet.binance.vision'
        else:
            self.BASE_URL = 'https://api.binance.com'

        # Initialize the Binance client with API keys
        self.client = Client(
            api_key=self.api_key,
            api_secret=self.api_secret,
            testnet=self.testnet
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
    async def cancel_all_orders_async(self, symbol):
        """Cancel all open orders for a symbol asynchronously."""
        endpoint = '/api/v3/openOrders'
        timestamp = int(time.time() * 1000)
        params = {
            'symbol': symbol,
            'timestamp': str(timestamp)
        }

        # Create signature
        query_string = '&'.join([f"{key}={value}" for key, value in params.items()])
        signature = hmac.new(self.api_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
        params['signature'] = signature

        headers = {
            'X-MBX-APIKEY': self.api_key
        }

        # Make DELETE request to cancel all orders
        try:
            async with self.session.delete(f"{self.BASE_URL}{endpoint}", params=params, headers=headers) as resp:
                response = await resp.json()
                if resp.status == 200:
                    logging.info(f"Successfully cancelled all orders for {symbol}")
                    return response
                else:
                    logging.error(f"Failed to cancel orders: {response}")
                    return None
        except Exception as e:
            logging.error(f"Error cancelling orders: {str(e)}")
            return None

    async def place_order_async(self, symbol, side, quantity, price, order_type='LIMIT', time_in_force='GTC', recvWindow=5000):
        """Place an order on Binance asynchronously with rate limiting."""
        async with self.order_semaphore:  # Implement rate limiting
            endpoint = '/api/v3/order'
            timestamp = int(time.time() * 1000)
            
            # Pre-format the price with proper precision
            price_str = f"{price:.8f}".rstrip('0').rstrip('.')
            quantity_str = f"{quantity:.8f}".rstrip('0').rstrip('.')
            
            params = {
                'symbol': symbol,
                'side': side.upper(),
                'type': order_type.upper(),
                'timeInForce': time_in_force,
                'quantity': quantity_str,
                'price': price_str,
                'recvWindow': recvWindow,
                'timestamp': str(timestamp)
            }
            
            # Create signature
            query_string = '&'.join([f"{key}={value}" for key, value in params.items()])
            signature = hmac.new(
                self.api_secret.encode('utf-8'),
                query_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            params['signature'] = signature

            try:
                async with self.session.post(
                    f"{self.BASE_URL}{endpoint}",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=5)  # Specific timeout for order placement
                ) as resp:
                    response = await resp.json()
                    if resp.status == 200:
                        return response
                    logging.error(f"Failed to place order: {response}")
                    return response
            except asyncio.TimeoutError:
                logging.error("Order placement timeout")
                return None
            except Exception as e:
                logging.error(f"Error placing order: {str(e)}")
                return None

    async def get_current_price_async(self, symbol: str) -> float:
        """Fetch the current price using existing session."""
        try:
            url = f"{self.BASE_URL}/api/v3/ticker/price"
            async with self.session.get(url, params={'symbol': symbol}) as response:
                if response.status == 200:
                    data = await response.json()
                    return float(data['price'])
                return None
        except Exception as e:
            logging.error(f"Error fetching price: {str(e)}")
            return None

    async def close(self):
        """Properly close the session."""
        if not self.session.closed:
            await self.session.close()

    async def get_account_async(self):
        """Get account information asynchronously."""
        loop = asyncio.get_event_loop()
        try:
            # Run the synchronous get_account method in a thread pool
            account_info = await loop.run_in_executor(
                None, 
                self.client.get_account
            )
            return account_info
        except Exception as e:
            logging.error(f"Error getting account info: {e}")
            raise

    def __del__(self):
        """Ensure session is closed on deletion."""
        if hasattr(self, 'session') and not self.session.closed:
            asyncio.create_task(self.session.close())

 