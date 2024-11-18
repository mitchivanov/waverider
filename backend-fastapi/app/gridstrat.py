import asyncio
import logging
from binance_client import BinanceClient
import aiohttp
from asyncio_throttle import Throttler
from binance_websocket import BinanceWebSocket
import os
import decimal
import time
from sqlalchemy import delete
import datetime
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import async_session
from models.models import TradeHistory, ActiveOrder
from sqlalchemy import update
from utils import OrderService

# Configure logging for the entire application
logging.basicConfig(
    level=logging.DEBUG,  # Set the default logging level to INFO
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='debug.log'
)

# Suppress debug messages from urllib3
logging.getLogger('urllib3').setLevel(logging.WARNING)

class GridStrategy:
    def __init__(
        self,
        symbol,
        asset_a_funds,
        asset_b_funds,
        grids,
        deviation_threshold,
        growth_factor,  # User-defined growth factor
        use_granular_distribution,  # User-defined flag for granular distribution
        trail_price=True,
        only_profitable_trades=False,
    ):
        # Securely retrieve API credentials from environment variables
        
        api_key = 'R1iPxmWzKPragpC2XspJITGIL3wmKqDPY8znltkOLyB7c8I4xyY6LnQI7ZVR5Qd2'
        api_secret = 'Ry4TT8syAN50NBURYsUY13cFZJ5r6NZJNAp5xkFKdFSr3uKMudxhCvlTP4eJZwCi'
        
        # Ensure the API key and secret are strings
        if not isinstance(api_key, str) or not isinstance(api_secret, str):
            raise ValueError("API key and secret must be strings")

        # Initialize the Binance client with your credentials
        self.binance_client = BinanceClient(api_key=api_key, api_secret=api_secret)
        self.symbol = symbol.upper()  # Ensure symbol is in uppercase for Binance API
        self.asset_a_funds = asset_a_funds
        self.asset_b_funds = asset_b_funds
        self.grids = grids
        self.deviation_threshold = deviation_threshold
        self.deviation = None
        self.initial_price = None
        self.trail_price = trail_price
        self.grid_levels = {'buy': [], 'sell': []}
        self.buy_positions = []
        self.sell_positions = []
        self.realized_profit_a = 0
        self.realized_profit_b = 0
        self.unrealized_profit_a = 0
        self.unrealized_profit_b = 0
        self.only_profitable_trades = only_profitable_trades
        self.session = None
        self.throttler = Throttler(rate_limit=5, period=1)
        self.current_price = None  # Initialize current price
        self.websocket = BinanceWebSocket(self.symbol)  # Initialize the WebSocket
        self.stop_flag = False  # Initialize the stop flag
        self.active_orders = []  # List to store active orders
        self.trade_history = []  # List to store completed trades
        self.growth_factor = growth_factor  # Store the growth factor
        self.use_granular_distribution = use_granular_distribution  # Store the flag for granular distribution
        self.open_trades = []

        # Extract and store base and quote assets
        self.base_asset = self.symbol[:-4]   # e.g., 'BTC' from 'BTCUSDT'
        self.quote_asset = self.symbol[-4:]  # e.g., 'USDT' from 'BTCUSDT'

        self.order_service = OrderService(
            binance_client=self.binance_client, 
            symbol=self.symbol,
            asset_a_funds=self.asset_a_funds,
            asset_b_funds=self.asset_b_funds
        )

        # Check account balance
        self.check_account_balance()

        # После существующих инициализаций
        self.start_time = datetime.datetime.now()
        
    def check_account_balance(self):
        """Check if the account balance is sufficient for the assigned funds."""
        account_info = self.binance_client.client.get_account()
        balances = {balance['asset']: float(balance['free']) for balance in account_info['balances']}

        # Extract base and quote assets from the symbol
        base_asset, quote_asset = self.symbol[:-4], self.symbol[-4:]

        # Check if there is enough balance for asset A (quote asset)
        if balances.get(quote_asset, 0) < self.asset_a_funds:
            raise ValueError(f"Insufficient balance for {quote_asset}. Required: {self.asset_a_funds}, Available: {balances.get(quote_asset, 0)}")

        # Check if there is enough balance for asset B (base asset)
        if balances.get(base_asset, 0) < self.asset_b_funds:
            raise ValueError(f"Insufficient balance for {base_asset}. Required: {self.asset_b_funds}, Available: {balances.get(base_asset, 0)}")

        logging.info(f"Sufficient balance for {quote_asset} and {base_asset}.")

    async def update_price(self):
        """Update the current price using the WebSocket."""
        try:
            await self.websocket.start()
            logging.info("WebSocket connection started.")
            async with self.websocket.bsm.symbol_ticker_socket(symbol=self.symbol.lower()) as stream:
                while True:
                    msg = await stream.recv()
                    if msg is None:
                        break  # Exit the loop if the stream is closed
                    self.current_price = float(msg['c'])  # 'c' is the current price in the message
        except Exception as e:
            logging.error(f"Error in update_price: {e}")
            await asyncio.sleep(5)  # Wait before retrying
            await self.update_price()  # Retry updating price
        finally:
            await self.websocket.stop()
            logging.info("WebSocket connection closed.")
                
    async def calculate_order_size(self):
        """Calculate the order sizes using linear distribution with a growth factor."""
        # Ensure current price is available
        if self.current_price is None:
            ticker = self.binance_client.client.get_ticker(symbol=self.symbol)
            self.current_price = float(ticker['lastPrice'])

        if self.use_granular_distribution:
            # Calculate buy order sizes using linear distribution
            total_buy_funds = self.asset_a_funds
            x1 = total_buy_funds / (self.grids + (self.growth_factor * (self.grids * (self.grids - 1)) / 2))
            self.buy_order_sizes = [
                (x1 + self.growth_factor * i * x1) / self.current_price  # <-- Change: Division by current_price
                for i in range(self.grids)
            ]

            # Debug logging for buy order sizes
            logging.debug(f"Total buy funds: {total_buy_funds} USDT")
            logging.debug(f"Growth factor: {self.growth_factor}")
            logging.debug(f"Initial buy order size (x1): {x1}")

            # Calculate sell order sizes using linear distribution
            total_sell_quantity = self.asset_b_funds
            x1_sell = total_sell_quantity / (self.grids + (self.growth_factor * (self.grids * (self.grids - 1)) / 2))
            self.sell_order_sizes = [x1_sell + self.growth_factor * i * x1_sell for i in range(self.grids)]

            # Debug logging for sell order sizes
            logging.debug(f"Total sell quantity: {total_sell_quantity} BTC")
            logging.debug(f"Initial sell order size (x1_sell): {x1_sell}")
        else:
            # Calculate buy order sizes (equal distribution)
            total_buy_funds = self.asset_a_funds
            buy_funds_per_grid = total_buy_funds / self.grids
            self.buy_order_sizes = [buy_funds_per_grid / price for price in self.grid_levels['buy']]

            # Debug logging for equal distribution
            logging.debug(f"Buy funds per grid: {buy_funds_per_grid} USDT")

            # Calculate sell order sizes (equal distribution)
            total_sell_quantity = self.asset_b_funds
            sell_quantity_per_grid = total_sell_quantity / self.grids
            self.sell_order_sizes = [sell_quantity_per_grid] * len(self.grid_levels['sell'])

            # Debug logging for equal distribution
            logging.debug(f"Sell quantity per grid: {sell_quantity_per_grid} BTC")

        logging.info("Calculated order sizes for each grid level.")
        for i, price in enumerate(self.grid_levels['buy']):
            logging.info(f"Buy Level {i+1}: Price = {price}, Order Size = {self.buy_order_sizes[i]} BTC")

        for i, price in enumerate(self.grid_levels['sell']):
            logging.info(f"Sell Level {i+1}: Price = {price}, Order Size = {self.sell_order_sizes[i]} BTC")

    async def calculate_grid_levels(self, current_price):
        """Calculate grid levels based on current price and deviation threshold."""
        logging.info("Calculating grid levels based on the current price and deviation threshold.")
        step_distance = (self.deviation_threshold / self.grids) * current_price
        # Calculate buy levels (below current price) and sell levels (above current price)
        self.grid_levels['buy'] = [
            current_price - (i * step_distance) for i in range(1, self.grids + 1)
        ]
        self.grid_levels['sell'] = [
            current_price + (i * step_distance) for i in range(1, self.grids + 1)
        ]
        logging.info(f"Buy levels: {self.grid_levels['buy']}")
        logging.info(f"Sell levels: {self.grid_levels['sell']}")

    async def place_limit_order(self, price, order_type, order_size, recvWindow=2000):
        """Place a limit order with proper error handling and validation."""
        return await self.order_service.place_limit_order(price, order_type, order_size, recvWindow)

    async def place_batch_orders(self):
        """Place initial buy and sell orders based on grid levels in batches."""
        try:
            batch_size = 5  # Place orders in batches to avoid rate limits
            logging.info("Starting to place batch orders for initial grid levels.")
            
            for order_type in ['buy', 'sell']:
                levels = self.grid_levels[order_type]
                order_sizes = self.buy_order_sizes if order_type == 'buy' else self.sell_order_sizes
                total_orders = len(levels)
                successful_orders = 0
                failed_orders = 0
                retry_orders = []

                for i in range(0, total_orders, batch_size):
                    batch_levels = levels[i:i + batch_size]
                    batch_sizes = order_sizes[i:i + batch_size]
                    
                    logging.info(f"Attempting to place batch of {len(batch_levels)} {order_type.upper()} orders "
                               f"for levels: {batch_levels[0]:.2f} to {batch_levels[-1]:.2f}")

                    for level_price, order_size in zip(batch_levels, batch_sizes):
                        try:
                            # Verify balance before placing order
                            if not self.is_balance_sufficient(order_type, level_price, order_size):
                                logging.error(f"Insufficient balance for {order_type} order at {level_price}")
                                failed_orders += 1
                                retry_orders.append((level_price, order_size))
                                continue

                            # Place order with increased recvWindow
                            result = await self.place_limit_order(level_price, order_type, order_size)
                            logging.debug(f"Binance API Response: {result}")
                            if result and 'orderId' in result:
                                successful_orders += 1
                                logging.info(f"Successfully placed {order_type.upper()} order at ${level_price:.2f}")
                            else:
                                failed_orders += 1
                                retry_orders.append((level_price, order_size))
                                logging.error(f"Failed to place {order_type.upper()} order at ${level_price:.2f}")
                                
                        except Exception as e:
                            failed_orders += 1
                            retry_orders.append((level_price, order_size))
                            logging.error(f"Error placing {order_type.upper()} order at ${level_price:.2f}: {str(e)}")

                    # Log batch results with correct counts
                    logging.info(f"Placed {order_type.upper()} orders for levels: {batch_levels[0]:.2f} to {batch_levels[-1]:.2f}.")
                    logging.info(f"Successful orders: {successful_orders}, Failed orders: {failed_orders}")
                    
                    # Add delay between batches
                    await asyncio.sleep(1)

                # Retry failed orders with increased recvWindow
                if retry_orders:
                    logging.info(f"Attempting to retry {len(retry_orders)} failed {order_type.upper()} orders")
                    for price, size in retry_orders:
                        try:
                            if not self.is_balance_sufficient(order_type, price, size):
                                logging.error(f"Insufficient balance for retry of {order_type} order at {price}")
                                continue

                            result = await self.place_limit_order(price, order_type, size, recvWindow=60000)
                            if result and 'orderId' in result:
                                successful_orders += 1
                                failed_orders -= 1
                                logging.info(f"Successfully placed retry {order_type.upper()} order at ${price:.2f}")
                            await asyncio.sleep(0.5)
                        except Exception as e:
                            logging.error(f"Error in retry of {order_type.upper()} order at ${price:.2f}: {str(e)}")

                # Final status check with accurate counts
                logging.info(f"Final order placement status for {order_type.upper()}:")
                logging.info(f"Total successful: {successful_orders}, Total failed: {failed_orders}")

        except Exception as e:
            logging.error(f"Error in place_batch_orders: {e}")
            raise

    async def execute_strategy(self):
        """Execute the grid trading strategy with continuous monitoring."""
        logging.info("Starting the grid trading strategy execution.")
        
        
        price_update_task = None
        
        
        try:
            # Создаем одну сессию на все время работы стратегии
            self.session = aiohttp.ClientSession()
            price_update_task = asyncio.create_task(self.update_price())
            
            last_checked_price = None  # Track the last checked price
            
            while not self.stop_flag:
                start_time = time.time()  # Record the start time of the loop

                # Log message indicating waiting for price update
                logging.info("Waiting for current price to update...")

                # Ensure the current price is updated
                if self.current_price is not None and self.current_price != last_checked_price:
                    last_checked_price = self.current_price  # Update the last checked price

                    if self.initial_price is None:
                        self.initial_price = self.current_price
                        logging.info(f"Initial price set to ${self.initial_price:.2f}. Calculating grid levels and order sizes.")
                        
                        # Calculate grid levels first
                        await self.calculate_grid_levels(self.initial_price)
                        
                        # Then calculate order sizes
                        await self.calculate_order_size()
                        
                        await self.place_batch_orders()
                    # Calculate the deviation from the initial price
                    deviation = (self.current_price - self.initial_price) / self.initial_price

                    self.deviation = deviation

                    # Log the current price and deviation
                    logging.info(f"Current price: ${self.current_price:.2f}. Deviation: {deviation:.2%}.")

                    # Define tasks for checking buy and sell orders
                    async def check_buy_orders():
                        for buy in list(self.buy_positions):
                            if self.current_price <= buy['price']:
                                logging.info(f"Buy order filled at price ${buy['price']:.2f}")
                                # Remove the filled buy order from active orders
                                await self.remove_active_order(buy['order_id'])
                                
                                # Place the corresponding sell order
                                sell_price = buy['price'] + ((self.deviation_threshold / self.grids) * self.initial_price)
                                sell_order = await self.place_limit_order(sell_price, 'sell', buy['quantity'])
                                self.buy_positions.remove(buy)
                                
                                # Get the quote asset (USDT) from the trading pair
                                quote_asset = self.symbol[-4:]  # e.g., 'USDT' from 'BTCUSDT'
                                
                                # Record the trade as 'OPEN' with zero profit
                                await self.add_trade_to_history(
                                    buy_price=buy['price'],
                                    sell_price=None,
                                    quantity=buy['quantity'],
                                    profit=0,
                                    profit_asset=quote_asset,  # Use quote asset (USDT) for buy-sell pairs
                                    status='OPEN',
                                    trade_type='BUY_SELL'
                                )
                                # Track the open trade
                                self.open_trades.append({
                                    'buy_order': buy,
                                    'sell_order': {
                                        'price': sell_price,
                                        'quantity': buy['quantity'],
                                        'order_id': sell_order['orderId'] if sell_order else None
                                    },
                                    'trade_type': 'BUY_SELL'
                                })
                                logging.info(f"Placed corresponding sell order at price ${sell_price:.2f}")

                    async def check_sell_orders():
                        for sell in list(self.sell_positions):
                            if self.current_price >= sell['price']:
                                logging.info(f"Sell order filled at price ${sell['price']:.2f}")
                                # Remove the filled sell order from active orders
                                await self.remove_active_order(sell['order_id'])
                                
                                # Place the corresponding buy order
                                buy_price = sell['price'] - ((self.deviation_threshold / self.grids) * self.initial_price)
                                buy_order = await self.place_limit_order(buy_price, 'buy', sell['quantity'])
                                self.sell_positions.remove(sell)
                                
                                # Get the base asset (BTC) from the trading pair
                                base_asset = self.symbol[:-4]  # e.g., 'BTC' from 'BTCUSDT'
                                
                                # Record the trade as 'OPEN' with zero profit
                                await self.add_trade_to_history(
                                    buy_price=None,
                                    sell_price=sell['price'],
                                    quantity=sell['quantity'],
                                    profit=0,
                                    profit_asset=base_asset,  # Use base asset (BTC) for sell-buy pairs
                                    status='OPEN',
                                    trade_type='SELL_BUY'
                                )
                                # Track the open trade
                                self.open_trades.append({
                                    'sell_order': sell,
                                    'buy_order': {
                                        'price': buy_price,
                                        'quantity': sell['quantity'],
                                        'order_id': buy_order['orderId'] if buy_order else None
                                    },
                                    'trade_type': 'SELL_BUY'
                                })
                                logging.info(f"Placed corresponding buy order at price ${buy_price:.2f}")

                    await asyncio.gather(check_buy_orders(), check_sell_orders())
                                        
                    # Check open trades
                    await self.check_open_trades()

                    # Log summary of the checks
                    logging.info(f"Summary: {len(self.buy_positions)} buy orders and {len(self.sell_positions)} sell orders checked.")

                    # Reset grid if deviation threshold is reached
                    if abs(deviation) >= self.deviation_threshold:
                        logging.info("Deviation threshold reached. Resetting grid.")
                        await self.cancel_all_orders()
                        await self.reset_grid(self.current_price)

                # Sleep asynchronously to wait before the next price check
                await asyncio.sleep(1)
        except Exception as e:
            logging.error(f"Error in strategy execution: {str(e)}")
        finally:
            # Закрываем сессии только при завершении стратегии
            if price_update_task:
                await price_update_task
            await self.stop_strategy()

    async def reset_grid(self, new_initial_price):
        """Reset the grid when the deviation threshold is reached."""
        logging.info(
            f"Resetting grid with new initial price at ${new_initial_price:.2f}."
        )
        self.initial_price = new_initial_price  # Update the initial price
        await self.calculate_grid_levels(self.initial_price)  # Recalculate grid levels based on the new price
        await self.place_batch_orders()  # Place new orders after resetting the grid

    async def cancel_all_orders(self):
        """Cancel all open orders."""
        async with self.throttler:
            try:
                logging.info("Attempting to cancel all open orders.")
                # Отменяем ордера на бирже
                cancelled_orders = await self.binance_client.cancel_all_orders_async(self.symbol)
                
                if cancelled_orders:
                    logging.info(f"All open orders for {self.symbol} have been cancelled.")
                else:
                    logging.warning(f"No open orders to cancel for {self.symbol}.")
                
                # Удаляем из базы данных
                async with async_session() as session:
                    await session.execute(delete(ActiveOrder))
                    await session.commit()
                
                # Очищаем список в памяти
                self.active_orders.clear()
                self.trade_history.clear()
                
                logging.info(f"All open orders for {self.symbol} have been cancelled.")
            except Exception as e:
                logging.error(f"Error cancelling orders: {str(e)}")

    def extract_filters(self, exchange_info):
        """Extract necessary filters from exchange_info."""
        filters = exchange_info.get('filters', [])
        min_price = max_price = tick_size = None
        min_qty = max_qty = step_size = None
        min_notional = max_notional = None

        for f in filters:
            filter_type = f['filterType']
            if filter_type == 'PRICE_FILTER':
                min_price = float(f['minPrice'])
                max_price = float(f['maxPrice'])
                tick_size = float(f['tickSize'])
            elif filter_type == 'LOT_SIZE':
                min_qty = float(f['minQty'])
                max_qty = float(f['maxQty'])
                step_size = float(f['stepSize'])
            elif filter_type == 'NOTIONAL':
                min_notional = float(f.get('minNotional', 0))
                max_notional = float(f.get('maxNotional', float('inf')))

        # Check if any of the filters are missing
        if None in (min_price, max_price, tick_size, min_qty, max_qty, step_size, min_notional, max_notional):
            logging.error("One or more necessary filters are missing for symbol: {}".format(self.symbol))
            return None  # You can raise an exception here if preferred

        return {
            'min_price': min_price,
            'max_price': max_price,
            'tick_size': tick_size,
            'min_qty': min_qty,
            'max_qty': max_qty,
            'step_size': step_size,
            'min_notional': min_notional,
            'max_notional': max_notional
        }

    def is_balance_sufficient(self, order_type, price, quantity):
        """Check if there is sufficient balance to place the order."""
        try:
            # Use the same synchronous method as in check_account_balance
            account_info = self.binance_client.client.get_account()
            balances = {
                balance['asset']: float(balance['free']) 
                for balance in account_info['balances']
            }

            quote_asset = self.symbol[-4:]  # e.g., 'USDT'
            base_asset = self.symbol[:-4]   # e.g., 'BTC'

            if order_type.lower() == 'buy':
                required_quote = price * quantity
                available_quote = balances.get(quote_asset, 0)
                
                if available_quote < required_quote:
                    logging.warning(
                        f"Insufficient {quote_asset} balance. "
                        f"Required: {required_quote:.8f}, Available: {available_quote:.8f}"
                    )
                    return False
                    
            elif order_type.lower() == 'sell':
                required_base = quantity
                available_base = balances.get(base_asset, 0)
                
                if available_base < required_base:
                    logging.warning(
                        f"Insufficient {base_asset} balance. "
                        f"Required: {required_base:.8f}, Available: {available_base:.8f}"
                    )
                    return False

            return True

        except Exception as e:
            logging.error(f"Error checking balance: {e}")
            return True  # Allow the exchange to handle insufficient balance

    async def check_open_trades(self):
        """Periodically check if the second leg of each open trade has been executed."""
        logging.info("Starting check of open trades")
        for trade in list(self.open_trades):
            logging.info(f"Checking trade details: {trade}")
            try:
                # Check for buy-sell sequence trades
                if 'buy_order' in trade and 'sell_order' in trade and trade['trade_type'] == 'BUY_SELL':
                    logging.info("Processing BUY_SELL trade sequence")
                    buy_order = trade['buy_order']
                    sell_order = trade['sell_order']
                    order_status = await self.get_order_status(self.symbol, buy_order.get('order_id'))
                    logging.info(f"Buy order status: {order_status}")
                    
                    if order_status == 'FILLED':
                        logging.info("Buy order is filled, processing sell order")
                        # Remove the completed buy order from active orders
                        await self.remove_active_order(buy_order.get('order_id'))
                        
                        # Calculate profit in USDT for buy-sell sequence
                        buy_price = trade['buy_order']['price']
                        sell_price = sell_order['price']
                        quantity = sell_order['quantity']
                        profit_usdt = (sell_price - buy_price) * quantity
                        self.realized_profit_a += profit_usdt
                        
                        # Extract quote asset (USDT) from symbol
                        quote_asset = self.symbol[-4:]
                    
                        logging.info(f"Trade completed - Buy price: {buy_price}, Sell price: {sell_price}")
                        logging.info(f"Realized profit from buy-sell pair: ${profit_usdt:.2f} {quote_asset}")
                        
                        # Update trade history with completed trade
                        await self.update_trade_in_history(
                            buy_price=buy_price,
                            sell_price=sell_price,
                            quantity=quantity,
                            profit=profit_usdt,
                            profit_asset=quote_asset,
                            status='CLOSED',
                            trade_type=trade['trade_type']
                        )
                        self.open_trades.remove(trade)
                        logging.info("BUY_SELL trade successfully closed and recorded")
                        
                # Check for sell-buy sequence trades        
                elif 'sell_order' in trade and 'buy_order' in trade and trade['trade_type'] == 'SELL_BUY':
                    logging.info("Processing SELL_BUY trade sequence")
                    buy_order = trade['buy_order']
                    sell_order = trade['sell_order']
                    order_status = await self.get_order_status(self.symbol, sell_order.get('order_id'))
                    logging.info(f"Sell order status: {order_status}")
                    
                    if order_status == 'FILLED':
                        logging.info("Sell order is filled, processing buy order")
                        # Remove the completed sell order from active orders
                        await self.remove_active_order(sell_order.get('order_id'))
                        
                        # Calculate profit in base asset for sell-buy sequence
                        sell_price = trade['sell_order']['price']
                        buy_price = buy_order['price']
                        quantity = buy_order['quantity']
                        profit_btc = quantity * ((sell_price / buy_price) - 1)
                        self.realized_profit_b += profit_btc
                        
                        # Extract base asset from symbol
                        base_asset = self.symbol[:-4]
                        
                        logging.info(f"Trade completed - Sell price: {sell_price}, Buy price: {buy_price}")
                        logging.info(f"Realized profit from sell-buy pair: {profit_btc:.8f} {base_asset}")
                        
                        # Update trade history with completed trade
                        await self.update_trade_in_history(
                            buy_price=buy_price,
                            sell_price=sell_price,
                            quantity=quantity,
                            profit=profit_btc,
                            profit_asset=base_asset,
                            status='CLOSED',
                            trade_type=trade['trade_type']
                        )
                        self.open_trades.remove(trade)
                        logging.info("SELL_BUY trade successfully closed and recorded")
                        
            except Exception as e:
                logging.error(f"Error processing trade: {e}")
                logging.exception("Full traceback for trade processing error:")
                                                     
    async def get_order_status(self, symbol, order_id):
        """Checks the status of an order from the exchange."""
        async with self.throttler:
            try:
                order = self.binance_client.client.get_order(
                    symbol=symbol,
                    orderId=order_id
                )
                return order['status']
            except Exception as e:
                logging.error(f"Error fetching order status for order {order_id}: {e}")
                return None

    async def close_all_sessions(self):
        """Закрывает все активны сессии."""
        try:
            if hasattr(self, 'session') and self.session:
                await self.session.close()
                self.session = None
                
            if hasattr(self, 'binance_client'):
                await self.binance_client.close()
                
            if hasattr(self, 'websocket'):
                await self.websocket.stop()
                
            # Закрываем все WebSocket соединения
            for connection in self.active_connections[:]:
                try:
                    await connection.close()
                except Exception as e:
                    logging.error(f"Ошибка закрытия WebSocket соединения: {e}")
                self.active_connections.remove(connection)
                
        except Exception as e:
            logging.error(f"Ошибка при закрытии сессий: {e}")


# TRASH

    def get_assets_from_symbol(self):
        """Helper method to get base and quote assets from the trading pair symbol."""
        return {
            'base': self.base_asset,
            'quote': self.quote_asset
        }
        
            
# DATABASE OPERATIONS

    async def add_trade_to_history(self, buy_price, sell_price, quantity, profit, profit_asset, status, trade_type):
        """Добавляет завершенную сделку в историю."""
        try:
            logging.info(f"Попытка добавить сделку в историю: buy_price={buy_price}, sell_price={sell_price}, quantity={quantity}")
            
            trade_data = {
                'buy_price': buy_price,
                'sell_price': sell_price,
                'quantity': quantity,
                'profit': profit,
                'profit_asset': profit_asset,
                'status': status,
                'trade_type': trade_type,
                'executed_at': datetime.datetime.now()
            }
            
            # Add to local history
            try:
                self.trade_history.append(trade_data)
                logging.debug("Сделка успешно добавлена в локальную историю")
            except Exception as e:
                logging.error(f"Ошибка при добавлении в локальную историю: {e}")
                raise
            
            # Add to the database
            try:
                async with async_session() as session:
                    trade = TradeHistory(
                        buy_price=buy_price,
                        sell_price=sell_price,
                        quantity=quantity,
                        profit=profit,
                        profit_asset=profit_asset,
                        status=status,
                        trade_type=trade_type,
                        executed_at=datetime.datetime.now()
                    )
                    session.add(trade)
                    await session.commit()
                    logging.info(f"Сделка успешно добавлена в базу данных: {trade}")
            except Exception as e:
                logging.error(f"Ошибка при добавлении сделки в базу данных: {e}")
                raise
                
        except Exception as e:
            logging.error(f"Критическая ошибка в add_trade_to_history: {e}")
            raise

    async def add_active_order(self, order_data):
        """Добавляет активный ордер в базу данных и локальный список."""
        try:
            # Создаем объект ActiveOrder
            active_order = ActiveOrder(
                order_id=order_data["order_id"],  # Изменено с orderId
                order_type=order_data["order_type"],  # Изменено с side
                price=float(order_data["price"]),
                quantity=float(order_data["quantity"]),  # Изменено с origQty
                created_at=datetime.datetime.now()
            )
            
            # Сохраняем в базу данных
            async with async_session() as session:
                # Проверяем существование ордера
                existing_order = await session.execute(
                    select(ActiveOrder).where(ActiveOrder.order_id == active_order.order_id)
                )
                if existing_order.scalar_one_or_none():
                    # Если ордер существует, обновляем его
                    await session.execute(
                        update(ActiveOrder)
                        .where(ActiveOrder.order_id == active_order.order_id)
                        .values(
                            order_type=active_order.order_type,
                            price=active_order.price,
                            quantity=active_order.quantity,
                            created_at=active_order.created_at
                        )
                    )
                else:
                    # Если ордера нет, добавляем новый
                    session.add(active_order)
                
                await session.commit()
                
            # Обновляем локальный список
            self.active_orders = [order for order in self.active_orders if order["order_id"] != active_order.order_id]
            self.active_orders.append({
                "order_id": active_order.order_id,
                "order_type": active_order.order_type,
                "price": active_order.price,
                "quantity": active_order.quantity,
                "created_at": str(active_order.created_at)
            })
            
            
        except Exception as e:
            logging.error(f"Ошибка при сохранении активного ордера: {e}")

    async def update_trade_in_history(self, buy_price, sell_price, quantity, profit, profit_asset, status, trade_type):
        """Updates an existing trade in the history when it is closed."""
        async with async_session() as session:
            try:
                # Добавляем ORDER BY executed_at DESC чтобы получить самую последнюю сделку
                result = await session.execute(
                    select(TradeHistory).where(
                        TradeHistory.buy_price == buy_price,
                        TradeHistory.quantity == quantity,
                        TradeHistory.status == 'OPEN'
                    ).order_by(TradeHistory.executed_at.desc()).limit(1)
                )
                trade = result.scalar_one_or_none()
                
                if trade:
                    trade.sell_price = sell_price
                    trade.profit = profit
                    trade.profit_asset = profit_asset
                    trade.status = status
                    trade.executed_at = datetime.datetime.utcnow()
                    await session.commit()
                    
                    # Update in local history
                    for t in self.trade_history:
                        if (t['buy_price'] == buy_price and 
                            t['quantity'] == quantity and 
                            t['status'] == 'OPEN'):
                            t.update({
                                'sell_price': sell_price,
                                'profit': profit,
                                'profit_asset': profit_asset,
                                'status': status,
                                'executed_at': trade.executed_at,
                                'trade_type': trade_type
                            })
                            break
                else:
                    logging.warning(f"No open trade found with buy_price={buy_price}, quantity={quantity}")
                    
            except Exception as e:
                logging.error(f"Error updating trade history: {e}")
                await session.rollback()
                raise

    async def remove_active_order(self, order_id):
        """Удаляет ордер из списка активных ордеров."""
        try:
            # Удаляем из базы данных
            async with async_session() as session:
                await session.execute(
                    delete(ActiveOrder).where(ActiveOrder.order_id == order_id)
                )
                await session.commit()
                
            # Удаляем из списка в памяти
            self.active_orders = [order for order in self.active_orders if order['order_id'] != order_id]
            logging.info(f"Ордер {order_id} успешно удален из списка активных")
            
        except Exception as e:
            logging.error(f"Ошибка при удалении активного ордера {order_id}: {e}")


# ENDPOINTS UTILITIES

    def get_total_profit_usdt(self):
        """Calculate total profit in USDT by converting profits in base asset to USDT."""
        if self.current_price:
            profit_b_in_usdt = self.realized_profit_b * self.current_price
        else:
            profit_b_in_usdt = 0
        total_profit_usdt = self.realized_profit_a + profit_b_in_usdt
        return total_profit_usdt

    def calculate_unrealized_profit_loss(self):
        """Calculate unrealized profit or loss from open trades."""
        unrealized_profit_a = 0
        unrealized_profit_b = 0

        # For buy positions (waiting to sell)
        for trade in self.open_trades:
            if 'buy_order' in trade and 'sell_order' in trade:
                buy_price = trade['buy_order']['price']
                quantity = trade['buy_order']['quantity']
                # Unrealized profit in USDT
                profit_a = (self.current_price - buy_price) * quantity
                unrealized_profit_a += profit_a

        # For sell positions (waiting to buy)
        for trade in self.open_trades:
            if 'sell_order' in trade and 'buy_order' in trade:
                sell_price = trade['sell_order']['price']
                quantity = trade['sell_order']['quantity']
                # Unrealized profit in BTC
                profit_b = quantity * ((sell_price / self.current_price) - 1)
                unrealized_profit_b += profit_b

        # Convert BTC unrealized profit to USDT
        total_unrealized_profit_usdt = unrealized_profit_a + (unrealized_profit_b * self.current_price)

        result = {
            "unrealized_profit_a": unrealized_profit_a,
            "unrealized_profit_b": unrealized_profit_b,
            "total_unrealized_profit_usdt": total_unrealized_profit_usdt
        }
        
        return result


# ENDPOINTS

    async def get_strategy_status(self):
        """Получает текущий статус стратегии."""
        current_time = datetime.datetime.now()
        running_time = current_time - self.start_time if hasattr(self, 'start_time') else None
        total_profit_usdt = self.get_total_profit_usdt()
        unrealized_profit = self.calculate_unrealized_profit_loss()
        async with async_session() as session:
            result = await session.execute(select(ActiveOrder))
            active_orders = result.scalars().all()
            active_orders_count = len(active_orders)
        return {
            "status": "active" if not self.stop_flag else "inactive",
            "current_price": self.current_price,
            "initial_price": self.initial_price,
            "deviation": self.deviation,
            "realized_profit_a": self.realized_profit_a,
            "realized_profit_b": self.realized_profit_b,
            "total_profit_usdt": total_profit_usdt,
            "running_time": str(running_time) if running_time else None,
            "active_orders_count": active_orders_count,
            "completed_trades_count": len([t for t in self.trade_history if t['status'] == 'CLOSED']),
            "unrealized_profit": unrealized_profit,
            "active_orders": [
                {
                    "order_id": order["order_id"],
                    "order_type": order["order_type"],
                    "price": order["price"],
                    "quantity": order["quantity"],
                    "created_at": order["created_at"]
                } for order in self.active_orders
            ],
            "initial_parameters": {
                "symbol": self.symbol,
                "asset_a_funds": self.asset_a_funds,
                "asset_b_funds": self.asset_b_funds,
                "grids": self.grids,
                "deviation_threshold": self.deviation_threshold,
                "growth_factor": self.growth_factor,
                "use_granular_distribution": self.use_granular_distribution,
                "trail_price": self.trail_price,
                "only_profitable_trades": self.only_profitable_trades
            }
        }

    async def stop_strategy(self):
        """Останавливает стратегию и очищает все ресурсы."""
        try:
            # Устанаввием флаг остановки
            self.stop_flag = True
            
            # Отменяем все активные ордера
            await self.cancel_all_orders() 
        
            # Очищаем локальные списки
            self.active_orders = []
            self.buy_positions = []
            self.sell_positions = []
            self.open_trades = []
        
            # Очищаем таблицу активных ордеров в базе данных
            async with async_session() as session:
                await session.execute(delete(ActiveOrder))
                await session.commit()
            
            # Закрываем все сессии
            await self.close_all_sessions()
        
            logging.info("Стратегия успешно остановлена")
            return True
        
        except Exception as e:
            logging.error(f"Ошибка при остановке стратегии: {e}")
            raise e

    async def start_strategy(self):
        """Запускает торговую стратегию."""
        try:
            # Инициализация состояния
            self.stop_flag = False
            self.current_price = None
            self.initial_price = None
            self.realized_profit_a = 0
            self.realized_profit_b = 0
            
            # Создание сессий и подключений
            self.session = aiohttp.ClientSession()
            
            # Запуск основного цикла стратегии
            logging.info(f"Запуск стратегии для пары {self.symbol}")
            await self.execute_strategy()
            
            return True
        except Exception as e:
            logging.error(f"Ошибк при запуске стратегии: {e}")
            raise e

async def start_grid_strategy(parameters: dict) -> GridStrategy:
    """
    Создает и запускает экземпляр торговой стратегии.
    
    Args:
        parameters (dict): Параметры для инициализации стратегии
        
    Returns:
        GridStrategy: Запущенный экземпляр стратегии
    """
    try:
        strategy = GridStrategy(**parameters)
        asyncio.create_task(strategy.execute_strategy())
        return strategy
    except Exception as e:
        logging.error(f"Ошибка при запуске grid-стратегии: {e}")
        raise

async def stop_grid_strategy(strategy: GridStrategy) -> bool:
    """
    Останавливает работающую стратегию.
    
    Args:
        strategy (GridStrategy): Экземпляр работающей стратегии
        
    Returns:
        bool: True если остановка прошла успешно
    """
    try:
        strategy.stop_flag = True
        await strategy.cancel_all_orders()
        await strategy.close_all_sessions()
        logging.info("Grid strategy stopped successfully")
        return True
    except Exception as e:
        logging.error(f"Ошибка при остановке grid-стратегии: {e}")
        raise


#tratata