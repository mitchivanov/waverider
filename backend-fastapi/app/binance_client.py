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
    def __init__(self, api_key: str, api_secret: str, testnet: bool, bot_id: int = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.bot_id = bot_id
        
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
            logging.error(f"An error occurred while fetching the current price from Binance: {str(e)}")
            logging.error(f"Error type: {type(e).__name__}")
            logging.error(f"Error code: {getattr(e, 'code', 'N/A')}")
            logging.error(f"Error message: {getattr(e, 'message', str(e))}")
            # Вместо возврата None можно выбросить исключение
            raise

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
        
    async def cancel_all_orders_async(self, symbol, initial_only=False):
        """
        Cancel orders for a symbol asynchronously.
        
        Args:
            symbol (str): Trading pair symbol
            initial_only (bool): If True, cancel only initial orders. If False, cancel all orders.
        """
        endpoint = '/api/v3/openOrders'
        timestamp = int(time.time() * 1000)
        params = {
            'symbol': symbol,
            'timestamp': str(timestamp)
        }

        # Create signature
        query_string = '&'.join([f"{key}={value}" for key, value in params.items()])
        signature = hmac.new(self.api_secret.encode('utf-8'), 
                           query_string.encode('utf-8'), 
                           hashlib.sha256).hexdigest()
        params['signature'] = signature

        headers = {
            'X-MBX-APIKEY': self.api_key
        }

        try:
            # Сначала получаем список всех открытых ордеров
            async with self.session.get(f"{self.BASE_URL}/api/v3/openOrders", 
                                      params=params, 
                                      headers=headers) as resp:
                open_orders = await resp.json()
                
                if resp.status != 200:
                    logging.error(f"Failed to get open orders: {open_orders}")
                    return None

                cancelled_orders = []
                
                # Если initial_only=True, отменяем только initial ордера
                # В противном случае отменяем все ордера
                for order in open_orders:
                    if not initial_only or order.get('isInitial', False):
                        cancel_params = {
                            'symbol': symbol,
                            'orderId': order['orderId'],
                            'timestamp': str(int(time.time() * 1000))
                        }
                        
                        # Создаем подпись для каждого запроса отмены
                        cancel_query = '&'.join([f"{key}={value}" 
                                               for key, value in cancel_params.items()])
                        cancel_params['signature'] = hmac.new(
                            self.api_secret.encode('utf-8'),
                            cancel_query.encode('utf-8'),
                            hashlib.sha256
                        ).hexdigest()

                        async with self.session.delete(
                            f"{self.BASE_URL}/api/v3/order",
                            params=cancel_params,
                            headers=headers
                        ) as cancel_resp:
                            result = await cancel_resp.json()
                            if cancel_resp.status == 200:
                                cancelled_orders.append(result)
                            else:
                                logging.error(f"Failed to cancel order {order['orderId']}: {result}")

                if cancelled_orders:
                    logging.info(f"Successfully cancelled {len(cancelled_orders)} orders for {symbol}")
                    return cancelled_orders
                else:
                    logging.info(f"No {'initial ' if initial_only else ''}orders to cancel for {symbol}")
                    return []

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
                logging.error(f"Failed to fetch price: {await response.text()}")
                # Вместо возврата None можно выбросить исключение
                raise ValueError("Failed to fetch price")
        except Exception as e:
            logging.error(f"Error fetching price: {str(e)}")
            raise

    async def close(self):
        """Close the client session."""
        if hasattr(self, 'session') and not self.session.closed:
            await self.session.close()
            logging.info(f"Closed BinanceClient session for bot {self.bot_id}")

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

    async def cancel_orders_by_ids_async(self, symbol: str, order_ids: list):
        """
        Cancel specific orders by their IDs asynchronously.
        
        Args:
            symbol (str): Trading pair symbol
            order_ids (list): List of order IDs to cancel
        """
        cancelled_orders = []
        
        for order_id in order_ids:
            try:
                timestamp = int(time.time() * 1000)
                params = {
                    'symbol': symbol,
                    'orderId': order_id,
                    'timestamp': str(timestamp)
                }
                
                # Создаем подпись
                query_string = '&'.join([f"{key}={value}" for key, value in params.items()])
                signature = hmac.new(
                    self.api_secret.encode('utf-8'),
                    query_string.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                params['signature'] = signature

                async with self.session.delete(
                    f"{self.BASE_URL}/api/v3/order",
                    params=params,
                    headers={'X-MBX-APIKEY': self.api_key}
                ) as resp:
                    result = await resp.json()
                    if resp.status == 200:
                        cancelled_orders.append(result)
                        logging.info(f"Successfully cancelled order {order_id}")
                    else:
                        logging.error(f"Failed to cancel order {order_id}: {result}")

            except Exception as e:
                logging.error(f"Error cancelling order {order_id}: {str(e)}")
                
        return cancelled_orders if cancelled_orders else None

    async def get_order_status_async(self, symbol: str, order_id: int):
        """Get order status asynchronously."""
        endpoint = '/api/v3/order'
        timestamp = int(time.time() * 1000)
        
        params = {
            'symbol': symbol,
            'orderId': order_id,
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
            async with self.session.get(
                f"{self.BASE_URL}{endpoint}",
                params=params,
                headers={'X-MBX-APIKEY': self.api_key}
            ) as resp:
                if resp.status == 200:
                    order = await resp.json()
                    return order['status']
                logging.error(f"Failed to get order status: {await resp.text()}")
                return None
        except Exception as e:
            logging.error(f"Error getting order status: {str(e)}")
            return None


    async def is_balance_sufficient(self, base_asset: str, quote_asset: str, base_asset_funds: float, quote_asset_funds: float):
        """Check if the account balance is sufficient for the assigned funds."""
        account_info = self.client.get_account()
        balances = {balance['asset']: float(balance['free']) for balance in account_info['balances']}

        # Check if there is enough balance for asset A (quote asset)
        if balances.get(quote_asset, 0) < quote_asset_funds:
            raise ValueError(f"Insufficient balance for {quote_asset}. Required: {quote_asset_funds}, Available: {balances.get(quote_asset, 0)}")

        # Check if there is enough balance for asset B (base asset)
        if balances.get(base_asset, 0) < base_asset_funds:
            raise ValueError(f"Insufficient balance for {base_asset}. Required: {base_asset_funds}, Available: {balances.get(base_asset, 0)}")

        logging.info(f"Sufficient balance for {quote_asset} and {base_asset}.")
 