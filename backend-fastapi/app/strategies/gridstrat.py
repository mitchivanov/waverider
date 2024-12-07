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
from models.models import TradeHistory, ActiveOrder, OrderHistory
from sqlalchemy import update
import aiofiles
from strategies.base_strategy import BaseStrategy

from notifications import NotificationManager

# Configure logging for the entire application
logging.basicConfig(
    level=logging.DEBUG,  # Set the default logging level to INFO
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='debug.log'
)

# Suppress debug messages from urllib3
logging.getLogger('urllib3').setLevel(logging.WARNING)

class AsyncLogger:
    def __init__(self, bot_id, max_queue_size=1000):
        # Создаем пути для логов конкретного бота
        self.info_filename = f'logs/bot_{bot_id}/trades.log'
        self.debug_filename = f'logs/bot_{bot_id}/debug.log'
        
        # Создаем отдельные очереди для каждого уровня логирования
        self.info_queue = asyncio.Queue(maxsize=max_queue_size)
        self.debug_queue = asyncio.Queue(maxsize=max_queue_size)
        self.running = True
        
        # Создаем директорию для логов конкретного бота
        os.makedirs(os.path.dirname(self.info_filename), exist_ok=True)
        
        # Start the logging processes
        asyncio.create_task(self._process_logs(self.info_queue, self.info_filename))
        asyncio.create_task(self._process_logs(self.debug_queue, self.debug_filename))

    async def _write_immediately(self, message, filename):
        """Immediate writing to the specified log file"""
        try:
            async with aiofiles.open(filename, mode='a') as f:
                await f.write(message)
        except Exception as e:
            print(f"Critical error writing to log: {e}")
            
    async def fatal(self, message):
        """logging and immediate exit"""
        formatted_message = f"[{datetime.datetime.now().isoformat()}] [FATAL] {message}\n"
        await self._write_immediately(formatted_message, self.debug_filename)
        os._exit(1)  # Immediate exit
        
    async def panic(self, message):
        """logging and raising panic"""
        formatted_message = f"[{datetime.datetime.now().isoformat()}] [PANIC] {message}\n"
        await self._write_immediately(formatted_message, self.debug_filename)
        raise RuntimeError(f"Panic: {message}")
        
    async def log(self, message):
        """logging an info message"""
        await self.info_queue.put(f"[{datetime.datetime.now().isoformat()}] [INFO] {message}\n")
        
    async def debug(self, message):
        """logging a debug message"""
        await self.debug_queue.put(f"[{datetime.datetime.now().isoformat()}] [DEBUG] {message}\n")
        
    async def _process_logs(self, queue, filename):
        """Processes the log queue and writes messages to the specified file"""
        while self.running:
            try:
                # Collect all available logs
                messages = []
                messages.append(await queue.get())
                
                # Check if there are any more logs in the queue
                while not queue.empty() and len(messages) < 100:
                    try:
                        messages.append(queue.get_nowait())
                    except asyncio.QueueEmpty:
                        break
                
                # Write all collected logs at once
                async with aiofiles.open(filename, mode='a') as f:
                    await f.writelines(messages)
                    
            except Exception as e:
                print(f"Error writing to log file {filename}: {e}")
                await asyncio.sleep(1)
                
    async def close(self):
        """Closes the logger"""
        self.running = False
        # Wait for the remaining logs to be processed
        while not self.info_queue.empty() or not self.debug_queue.empty():
            await asyncio.sleep(0.1)

    async def error(self, message):
        """logging an error message"""
        formatted_message = f"[{datetime.datetime.now().isoformat()}] [ERROR] {message}\n"
        await self._write_immediately(formatted_message, self.debug_filename)

class GridStrategy(BaseStrategy):
    def __init__(
        self,
        bot_id,
        symbol,
        api_key,
        api_secret,
        testnet,
        asset_a_funds,
        asset_b_funds,
        grids,
        deviation_threshold,
        growth_factor,  # User-defined growth factor
        use_granular_distribution,  # User-defined flag for granular distribution
        trail_price=True,
        only_profitable_trades=False
    ):
        self.bot_id = bot_id
        # Securely retrieve API credentials from environment variables
        
        #api_key = '55euYhdLmx17qhTB1KhBSbrsS3A79bYU0C408VHMYsTTMcsyfSMboJ1d1uEWNLq3'
        #api_secret = '2zlWvVVQIrj5ZryMNCkt9KIqowlQQMdG0bcV4g4LAinOnF8lc7O3Udumn6rIAyLb'
        
        # Initialize the Binance client with your credentials
        self.binance_client = BinanceClient(api_key=api_key, api_secret=api_secret, testnet=testnet)
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

        # Check account balance
        self.check_account_balance()

        # После существующих инициализаций
        self.start_time = datetime.datetime.now()
        
        # Инициализируем логгер с ID бота
        self.trades_logger = AsyncLogger(bot_id)
        

        
        # Инициализируем текущую цену
        asyncio.create_task(self.update_current_price())

    async def update_current_price(self):
        while True:
            try:
                self.current_price = await self.binance_client.get_current_price_async(self.symbol)
                await asyncio.sleep(1)  # Update every second
                await self.trades_logger.log(f"Current price: {self.current_price}")
            except Exception as e:
                await self.trades_logger.panic(f"Error updating current price: {e}")
                await asyncio.sleep(5)  # Retry every 5 seconds in case of error

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
        await self.trades_logger.log("Calculating grid levels based on the current price and deviation threshold.")
        step_distance = (self.deviation_threshold / self.grids) * current_price
        # Calculate buy levels (below current price) and sell levels (above current price)
        self.grid_levels['buy'] = [
            current_price - (i * step_distance) for i in range(1, self.grids + 1)
        ]
        self.grid_levels['sell'] = [
            current_price + (i * step_distance) for i in range(1, self.grids + 1)
        ]
        await self.trades_logger.log(f"Buy levels: {self.grid_levels['buy']}")
        await self.trades_logger.log(f"Sell levels: {self.grid_levels['sell']}")

    async def place_limit_order(self, price, order_type, isInitial, order_size, recvWindow=2000):
        """Place a limit order with proper error handling and validation."""
        await self.trades_logger.log(f"Placing {order_type.upper()} order at ${price} for {order_size} units.")
        async with self.throttler:
            try:
                # Perform a balance check before placing the order
                if not self.is_balance_sufficient(order_type, price, order_size):
                    await self.trades_logger.fatal(f"Insufficient balance to place {order_type.upper()} order at ${price} for {order_size} units.")
                    return

                # Retrieve exchange info
                exchange_info = self.binance_client.client.get_symbol_info(self.symbol)
                if exchange_info is None:
                    await self.trades_logger.panic(f"Exchange information for symbol {self.symbol} not found.")
                    return

                # Extract filters
                filters = self.extract_filters(exchange_info)
                if filters is None:
                    await self.trades_logger.panic(f"Could not extract filters for symbol {self.symbol}.")
                    return

                # Unpack filter values
                min_price = filters['min_price']
                max_price = filters['max_price']
                tick_size = filters['tick_size']
                min_qty = filters['min_qty']
                max_qty = filters['max_qty']
                step_size = filters['step_size']
                min_notional = filters['min_notional']
                max_notional = filters['max_notional']

                # Function to calculate decimals based on tick size or step size
                def decimals(value):
                    return decimal.Decimal(str(value)).as_tuple().exponent * -1

                # Adjust price
                price_decimals = decimals(tick_size)
                price = round(price, price_decimals)

                # Adjust quantity
                qty_decimals = decimals(step_size)
                order_size = round(order_size, qty_decimals)

                # Ensure price is within min and max price
                if price < min_price or price > max_price:
                    await self.trades_logger.fatal(f"Price {price} is outside the allowed range ({min_price} - {max_price}).")
                    return

                # Ensure quantity is within min and max quantity
                if order_size < min_qty or order_size > max_qty:
                    await self.trades_logger.fatal(f"Quantity {order_size} is outside the allowed range ({min_qty} - {max_qty}).")
                    return

                # Ensure order notional is within min and max notional
                notional = price * order_size
                if notional < min_notional or notional > max_notional:
                    await self.trades_logger.fatal(f"Order notional ({notional}) is outside the allowed range ({min_notional} - {max_notional}).")
                    return

                # Log and place the order
                # logging.info(f"Attempting to place a single {order_type.upper()} order at ${price} for {order_size} units.")
                order = await self.binance_client.place_order_async(
                    self.symbol, order_type.upper(), order_size, price, recvWindow=recvWindow
                )
                
                await self.trades_logger.debug(f"Binance API Response: {order}")

                if order and 'orderId' in order:
                    order_id = order['orderId']
                    
                    logging.info(f"Attempting to add order {order_id} with isInitial={isInitial} to history")
                    
                    # Add to OrderHistory
                    await self.add_order_to_history(
                        bot_id=self.bot_id,
                        order_id=str(order_id),
                        order_type=order_type.lower(),
                        isInitial=isInitial,
                        price=price,
                        quantity=order_size,
                        status='OPEN'
                    )

                    # Update positions and active orders
                    if order_type.lower() == 'buy' and isInitial:
                        self.buy_positions.append({'price': price, 'quantity': order_size, 'order_id': order_id})
                    elif order_type.lower() == 'sell' and isInitial:
                        self.sell_positions.append({'price': price, 'quantity': order_size, 'order_id': order_id})
                    
                    order_data = {
                        'order_id': order_id,
                        'order_type': order_type,
                        'isInitial': isInitial,
                        'price': price,
                        'quantity': order_size
                    }

                    # Add to database
                    await self.add_active_order(self.bot_id, order_data)
                    
                    # Add to memory list
                    self.active_orders.append({
                        'order_id': order_id,
                        'order_type': order_type,
                        'price': price,
                        'quantity': order_size,
                        'created_at': datetime.datetime.now()
                    })
                    
                    # Return the order object
                    await self.trades_logger.log(f"Order {order_id} placed successfully")
                    return order

                elif order and order.get('code') == -1021:  # Timestamp for this request is outside of the recvWindow
                    # Retry with increased recvWindow
                    await self.trades_logger.panic(f"RecvWindow too small, retrying with increased window")
                    os.system('w32tm/resync')
                    return await self.place_limit_order(price, order_type, isInitial, order_size, recvWindow=5000)
                
                elif order and order.get('status') == 'EXPIRED_IN_MATCH':
                    # Handle EXPIRED_IN_MATCH by adjusting the price and retrying
                    adjustment_factor = 1.0001 if order_type.lower() == 'buy' else 0.9999
                    new_price = price * adjustment_factor
                    await self.trades_logger.log(f"Order expired in match. Retrying with new price: {new_price}")
                    return await self.place_limit_order(new_price, order_type, isInitial, order_size, recvWindow)
                else:
                    # Handle other API errors
                    error_code = order.get('code')
                    error_msg = order.get('msg')
                    await self.trades_logger.panic(f"Failed to place order: {error_code} - {error_msg}")
                    # Return None to indicate failure
                    return None
            except Exception as e:
                await self.trades_logger.panic(f"Error placing {order_type.upper()} order at ${price}: {str(e)}")
                # Return None to indicate exception occurred
                return None

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
                    
                    await self.trades_logger.log(f"Attempting to place batch of {len(batch_levels)} {order_type.upper()} orders "
                               f"for levels: {batch_levels[0]} to {batch_levels[-1]}")

                    for level_price, order_size in zip(batch_levels, batch_sizes):
                        try:
                            # Verify balance before placing order
                            if not self.is_balance_sufficient(order_type, level_price, order_size):
                                await self.trades_logger.error(f"Insufficient balance for {order_type} order at {level_price}")
                                failed_orders += 1
                                retry_orders.append((level_price, order_size))
                                continue

                            # Place order with increased recvWindow
                            result = await self.place_limit_order(price=level_price, order_type=order_type, isInitial=True, order_size=order_size)
                            await self.trades_logger.debug(f"Binance API Response: {result}")
                            if result and 'orderId' in result:
                                successful_orders += 1
                                await self.trades_logger.log(f"Successfully placed {order_type.upper()} order at ${level_price}")
                            else:
                                failed_orders += 1
                                retry_orders.append((level_price, order_size))
                                await self.trades_logger.error(f"Failed to place {order_type.upper()} order at ${level_price}")
                                
                        except Exception as e:
                            failed_orders += 1
                            retry_orders.append((level_price, order_size))
                            await self.trades_logger.error(f"Error placing {order_type.upper()} order at ${level_price}: {str(e)}")

                    # Log batch results with correct counts
                    await self.trades_logger.log(f"Placed {order_type.upper()} orders for levels: {batch_levels[0]} to {batch_levels[-1]}.")
                    await self.trades_logger.log(f"Successful orders: {successful_orders}, Failed orders: {failed_orders}")
                    
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

                            result = await self.place_limit_order(price=price, order_type=order_type, isInitial=True, order_size=size, recvWindow=60000)
                            if result and 'orderId' in result:
                                successful_orders += 1
                                failed_orders -= 1
                                logging.info(f"Successfully placed retry {order_type.upper()} order at ${price}")
                            await asyncio.sleep(0.5)
                        except Exception as e:
                            logging.error(f"Error in retry of {order_type.upper()} order at ${price}: {str(e)}")

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
                
                # Ensure the current price is updated
                if self.current_price is not None and self.current_price != last_checked_price:
                    last_checked_price = self.current_price

                    if self.initial_price is None:
                        
                        # Step 1: Set initial price
                        self.initial_price = self.current_price
                        await self.trades_logger.log(f"Initial price set to ${self.initial_price}. Calculating grid levels and order sizes.")
                        
                        # Step 2: Calculate grid levels first
                        await self.trades_logger.log(f"Calculating grid levels based on the current price and deviation threshold.")
                        await self.calculate_grid_levels(self.initial_price)
                        
                        # Step 3: Then calculate order sizes
                        await self.trades_logger.log(f"Calculating order sizes based on the current price and deviation threshold.")
                        await self.calculate_order_size()
                        
                        # Step 4: Place initial orders
                        await self.trades_logger.log(f"Placing initial orders based on the grid levels and order sizes.")
                        await self.place_batch_orders()
                        
                    # Periodically calculate the deviation from the initial price
                    deviation = (self.current_price - self.initial_price) / self.initial_price
                    self.deviation = deviation
                    
                    await self.trades_logger.log(f"Deviation from initial price: {deviation}")

                    # Define tasks for checking buy and sell orders
                    async def check_initial_buy_orders():
                        for buy in list(self.buy_positions):
                            try:
                                # Check order status via Binance API
                                order_status = await self.get_order_status(self.symbol, buy['order_id'])
                                await self.trades_logger.debug(f"Buy order {buy['order_id']} status: {order_status}")
                                
                                if order_status == 'FILLED':
                                    await self.trades_logger.log(f"Buy order {buy['order_id']} filled at price ${buy['price']}")
                                    
                                    # Update order status in history
                                    await self.update_order_history(self.bot_id, buy['order_id'], 'FILLED')
                                    
                                    # Delete buy position from tracking
                                    max_retries = 10
                                    retry_count = 0
                                    while retry_count < max_retries:
                                        try:
                                            self.buy_positions = [pos for pos in self.buy_positions if pos['order_id'] != buy['order_id']]
                                            await self.trades_logger.log(f"Buy position {buy['order_id']} removed from tracking")
                                            
                                            await self.remove_active_order(self.bot_id, buy['order_id'])
                                            await self.trades_logger.log(f"Buy order {buy['order_id']} removed")
                                            
                                            break
                                        except Exception as e:
                                            retry_count += 1
                                            if retry_count == max_retries:
                                                await self.trades_logger.log(f"Failed to remove active order after {max_retries} attempts: {e}")
                                                continue
                                            await asyncio.sleep(1 * retry_count)
                                    
                                    # Place corresponding sell order
                                    sell_price = buy['price'] + ((self.deviation_threshold / self.grids) * self.initial_price)
                                    
                                    retry_count = 0
                                    sell_order = None
                                    recvWindow = 5000
                                    while retry_count < max_retries:
                                        try:
                                            sell_order = await self.place_limit_order(
                                                price=sell_price,
                                                order_type='sell',
                                                isInitial=False,
                                                order_size=buy['quantity'],
                                                recvWindow=recvWindow
                                            )
                                            if sell_order and 'orderId' in sell_order:
                                                break
                                        except Exception as e:
                                            retry_count += 1
                                            if retry_count == max_retries:
                                                await self.trades_logger.log(f"Failed to place sell order after {max_retries} attempts: {e}")
                                                recvWindow += 5000
                                                continue
                                            await asyncio.sleep(1 * retry_count)
                                    
                                    if sell_order and 'orderId' in sell_order:
                                        try:
                                            quote_asset = self.symbol[-4:]
                                            
                                            # Write to trade history using data from Binance response
                                            trade = await self.add_trade_to_history(
                                                bot_id=self.bot_id,
                                                buy_price=buy['price'],
                                                sell_price=float(sell_order['price']),  # Use price from response
                                                quantity=float(sell_order['origQty']),  # Use quantity from response
                                                profit=0,
                                                profit_asset=quote_asset,
                                                status='OPEN',
                                                trade_type='BUY_SELL',
                                                buy_order_id=buy['order_id'],
                                                sell_order_id=sell_order['orderId']
                                            )
                                            
                                            # Track open trade with data from response
                                            self.open_trades.append({
                                                'id': trade.id,
                                                'buy_order': buy,
                                                'sell_order': {
                                                    'price': float(sell_order['price']),
                                                    'quantity': float(sell_order['origQty']),
                                                    'order_id': sell_order['orderId']
                                                },
                                                'trade_type': 'BUY_SELL'
                                            })
                                            await self.trades_logger.log(f"Successfully placed corresponding sell order at price ${sell_price}")
                                            
                                            
                                            notification_data = {
                                                "notification_type": "new_trade",
                                                "bot_id": self.bot_id,
                                                "payload": {
                                                    "trade_type": 'BUY_SELL',
                                                    "buy_price": buy['price'],
                                                    "sell_price": sell_price,
                                                    "quantity": buy['quantity'],
                                                    "symbol": self.symbol
                                                }
                                            }   
                                            
                                            await NotificationManager.send_notification("new_trade", self.bot_id, notification_data)
                                            
                                        except Exception as e:
                                            await self.trades_logger.log(f"Error processing trade data: {e}")
                                    else:
                                        await self.trades_logger.log("Failed to place sell order - skipping trade processing")
                                        
                            except Exception as e:
                                await self.trades_logger.log(f"Error in check_buy_orders: {e}")
                                continue

                    async def check_initial_sell_orders():
                        for sell in list(self.sell_positions):
                            try:
                                # Check order status via Binance API
                                order_status = await self.get_order_status(self.symbol, sell['order_id'])
                                await self.trades_logger.debug(f"Sell order {sell['order_id']} status: {order_status}")
                                
                                if order_status == 'FILLED':
                                    await self.trades_logger.log(f"Sell order {sell['order_id']} filled at price ${sell['price']}")
                                    
                                    # Update order status in history
                                    await self.update_order_history(self.bot_id, sell['order_id'], 'FILLED')
                                    
                                    # Delete sell position from tracking
                                    max_retries = 3
                                    retry_count = 0
                                    while retry_count < max_retries:
                                        try:
                                            self.sell_positions = [pos for pos in self.sell_positions if pos['order_id'] != sell['order_id']]
                                            await self.trades_logger.log(f"Sell position {sell['order_id']} removed from tracking")
                                            
                                            await self.remove_active_order(self.bot_id, sell['order_id'])
                                            await self.trades_logger.log(f"Sell order {sell['order_id']} removed")
                                            
                                            break
                                        
                                        except Exception as e:
                                            retry_count += 1
                                            if retry_count == max_retries:
                                                await self.trades_logger.log(f"Failed to remove active order after {max_retries} attempts: {e}")
                                                continue
                                            await asyncio.sleep(1 * retry_count)
                                    
                                    # Place corresponding buy order
                                    buy_price = sell['price'] - ((self.deviation_threshold / self.grids) * self.initial_price)
                                    
                                    retry_count = 0
                                    buy_order = None
                                    while retry_count < max_retries:
                                        try:
                                            buy_order = await self.place_limit_order(
                                                price=buy_price,
                                                order_type='buy',
                                                isInitial=False,
                                                order_size=sell['quantity']
                                            )
                                            if buy_order and 'orderId' in buy_order:
                                                break
                                        except Exception as e:
                                            retry_count += 1
                                            if retry_count == max_retries:
                                                await self.trades_logger.log(f"Failed to place buy order after {max_retries} attempts: {e}")
                                                continue
                                            await asyncio.sleep(1 * retry_count)
                                    
                                    if buy_order and 'orderId' in buy_order:
                                        try:
                                            base_asset = self.symbol[:-4]
                                            
                                            # Write to trade history using data from Binance response
                                            trade = await self.add_trade_to_history(
                                                bot_id=self.bot_id,
                                                buy_price=float(buy_order['price']),
                                                sell_price=sell['price'],
                                                quantity=float(buy_order['origQty']),
                                                profit=0,
                                                profit_asset=base_asset,
                                                status='OPEN',
                                                trade_type='SELL_BUY',
                                                buy_order_id=buy_order['orderId'],
                                                sell_order_id=sell['order_id']
                                            )
                                            
                                            # Track open trade
                                            self.open_trades.append({
                                                'id': trade.id,
                                                'sell_order': sell,
                                                'buy_order': {
                                                    'price': float(buy_order['price']),
                                                    'quantity': float(buy_order['origQty']),
                                                    'order_id': buy_order['orderId']
                                                },
                                                'trade_type': 'SELL_BUY'
                                            })
                                            
                                            notification_data = {
                                                "notification_type": "new_trade",
                                                "bot_id": self.bot_id,
                                                "payload": {
                                                    "trade_type": 'SELL_BUY',
                                                    "buy_price": float(buy_order['price']),
                                                    "sell_price": sell['price'],
                                                    "quantity": float(buy_order['origQty']),
                                                    "symbol": self.symbol
                                                }
                                            }
                                            
                                            await NotificationManager.send_notification("new_trade", self.bot_id, notification_data)
                                            
                                            await self.trades_logger.log(f"Successfully placed corresponding buy order at price ${buy_price}")
                                        except Exception as e:
                                            await self.trades_logger.log(f"Error processing trade data: {e}")
                                    else:
                                        await self.trades_logger.log("Failed to place buy order - skipping trade processing")
                                        
                            except Exception as e:
                                await self.trades_logger.log(f"Error in check_sell_orders: {e}")
                                continue

                    await asyncio.gather(check_initial_buy_orders(), check_initial_sell_orders())
                                        
                    # Check open trades
                    await self.check_open_trades()

                    # Log summary of the checks
                    await self.trades_logger.log(f"Summary: {len(self.buy_positions)} buy orders and {len(self.sell_positions)} sell orders checked.")

                    # Reset grid if deviation threshold is reached
                    if abs(deviation) >= self.deviation_threshold:
                        logging.info("Deviation threshold reached. Resetting grid.")
                        
                        await self.cancel_all_initial_orders()
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
            f"Resetting grid with new initial price at ${new_initial_price}."
        )
        self.initial_price = new_initial_price  # Update the initial price
        await self.calculate_grid_levels(self.initial_price)  # Recalculate grid levels based on the new price
        await self.place_batch_orders()  # Place new orders after resetting the grid

    async def cancel_all_initial_orders(self):
        """Cancel all initial orders and remove them from all tracking instances."""
        async with self.throttler:
            try:
                await self.trades_logger.log("Attempting to cancel all initial orders.")
                
                # Получаем список initial ордеров из базы данных
                async with async_session() as session:
                    result = await session.execute(
                        select(ActiveOrder).where(ActiveOrder.isInitial == True)
                    )
                    initial_orders = result.scalars().all()
                    
                    if not initial_orders:
                        await self.trades_logger.log(f"No initial orders found to cancel for {self.symbol}.")
                        return
                    
                    # Собираем ID всех initial ордеров
                    initial_order_ids = [order.order_id for order in initial_orders]
                    
                    try:
                        # Cancel all initial orders in one request
                        cancelled_orders = await self.binance_client.cancel_orders_by_ids_async(
                            symbol=self.symbol,
                            order_ids=initial_order_ids
                        )
                        
                        if cancelled_orders:
                            # Обновляем статус в истории и удаляем из всех инстанций
                            for order_id in initial_order_ids:
                                try:
                                    # 1. Update order status in history
                                    await self.update_order_history(self.bot_id, order_id, 'CANCELED')
                                    
                                    # 2. Remove from buy_positions
                                    self.buy_positions = [
                                        pos for pos in self.buy_positions 
                                        if str(pos['order_id']) != str(order_id)
                                    ]
                                    
                                    # 3. Remove from sell_positions
                                    self.sell_positions = [
                                        pos for pos in self.sell_positions 
                                        if str(pos['order_id']) != str(order_id)
                                    ]
                                    
                                    # 4. Remove from active_orders
                                    self.active_orders = [
                                        order for order in self.active_orders 
                                        if str(order['order_id']) != str(order_id)
                                    ]
                                    
                                    # 5. Delete from database
                                    await session.execute(
                                        delete(ActiveOrder).where(ActiveOrder.order_id == order_id)
                                    )
                                    await session.commit()
                                    
                                    await self.trades_logger.log(f"Order {order_id} successfully cancelled and removed from all tracking instances")
                                except Exception as e:
                                    await self.trades_logger.log(f"Error cancelling order {order_id}: {e}")
                        else:
                            await self.trades_logger.panic("Failed to cancel orders or no orders were cancelled")
                        
                    except Exception as e:
                        await self.trades_logger.log(f"Error cancelling orders: {e}")
                    
            except Exception as e:
                logging.error(f"Error in cancel_all_orders: {str(e)}")

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
        await self.trades_logger.log("Starting check of open trades")
        
        for trade in list(self.open_trades):
            await self.trades_logger.log(f"Now checking {trade['trade_type']} trade with details: {trade}. Trade id: {trade['id']}")
            try:
                # Check for buy-sell sequence trades
                if 'buy_order' in trade and 'sell_order' in trade and trade['trade_type'] == 'BUY_SELL':
                    buy_order = trade['buy_order']
                    sell_order = trade['sell_order']
                    order_status = await self.get_order_status(self.symbol, sell_order.get('order_id'))
                    await self.trades_logger.log(f"CHECKING {trade['id']} TRADE: Sell order status: {order_status}")
                    
                    if order_status == 'FILLED':
                        await self.trades_logger.log("Sell order is filled, processing sell order")
                        
                        # Update order status in history
                        await self.update_order_history(self.bot_id, sell_order.get('order_id'), 'FILLED')
                        
                        # Remove the completed buy order from active orders
                        await self.remove_active_order(self.bot_id, sell_order.get('order_id'))
                        
                        # Calculate profit in USDT for buy-sell sequence
                        buy_price = trade['buy_order']['price']
                        sell_price = sell_order['price']
                        quantity = sell_order['quantity']
                        profit_usdt = (sell_price - buy_price) * quantity
                        self.realized_profit_a += profit_usdt
                        
                        # Extract quote asset (USDT) from symbol
                        quote_asset = self.symbol[-4:]
                    
                        await self.trades_logger.log(f"Trade completed - Buy price: {buy_price}, Sell price: {sell_price}")
                        await self.trades_logger.log(f"Realized profit from buy-sell pair: ${profit_usdt} {quote_asset}")
                        
                        # Update trade history with completed trade
                        await self.update_trade_in_history(
                            bot_id=self.bot_id,
                            buy_price=buy_price,
                            sell_price=sell_price,
                            quantity=quantity,
                            profit=profit_usdt,
                            profit_asset=quote_asset,
                            status='CLOSED',
                            trade_type=trade['trade_type']
                        )
                        self.open_trades.remove(trade)
                        await self.trades_logger.log("BUY_SELL trade successfully closed and recorded")
                        

                # Check for sell-buy sequence trades        
                elif 'sell_order' in trade and 'buy_order' in trade and trade['trade_type'] == 'SELL_BUY':
                    buy_order = trade['buy_order']
                    sell_order = trade['sell_order']
                    order_status = await self.get_order_status(self.symbol, buy_order.get('order_id'))
                    await self.trades_logger.log(f"CHECKING {trade['id']} TRADE: Buy order status: {order_status}")
                    
                    if order_status == 'FILLED':
                        await self.trades_logger.log("Buy order is filled, processing buy order")
                        
                        # Update order status in history
                        await self.update_order_history(self.bot_id, buy_order.get('order_id'), 'FILLED')
                        
                        # Remove the completed sell order from active orders
                        await self.remove_active_order(self.bot_id, buy_order.get('order_id'))
                        
                        # Calculate profit in base asset for sell-buy sequence
                        sell_price = trade['sell_order']['price']
                        buy_price = buy_order['price']
                        quantity = buy_order['quantity']
                        profit_btc = quantity * ((sell_price / buy_price) - 1)
                        self.realized_profit_b += profit_btc
                        
                        # Extract base asset from symbol
                        base_asset = self.symbol[:-4]
                        
                        await self.trades_logger.log(f"Trade completed - Sell price: {sell_price}, Buy price: {buy_price}")
                        await self.trades_logger.log(f"Realized profit from sell-buy pair: {profit_btc:.8f} {base_asset}")
                        
                        # Update trade history with completed trade
                        await self.update_trade_in_history(
                            bot_id=self.bot_id,
                            buy_price=buy_price,
                            sell_price=sell_price,
                            quantity=quantity,
                            profit=profit_btc,
                            profit_asset=base_asset,
                            status='CLOSED',
                            trade_type=trade['trade_type']
                        )
                        self.open_trades.remove(trade)
                        await self.trades_logger.log("SELL_BUY trade successfully closed and recorded")
                        
            except Exception as e:
                await self.trades_logger.log(f"Error processing trade: {str(e)}")

    async def get_order_status(self, symbol, order_id):
        """Checks the status of an order from the exchange asynchronously."""
        async with self.throttler:
            try:
                status = await self.binance_client.get_order_status_async(
                    symbol=symbol,
                    order_id=order_id
                )
                if status:
                    return status
                return None
            except Exception as e:
                await self.trades_logger.panic(f"Error fetching order status for order {order_id}: {e}")
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

    async def add_trade_to_history(self, bot_id, buy_price, sell_price, quantity, profit, profit_asset, status, trade_type, buy_order_id=None, sell_order_id=None):
        try:
            logging.info(f"Попытка добавить сделку в историю: buy_price={buy_price}, sell_price={sell_price}, quantity={quantity}")
            
            trade_data = {
                'id': None,  # Будет заполнено после добавления в БД
                'bot_id': bot_id,
                'buy_price': buy_price,
                'sell_price': sell_price,
                'quantity': quantity,
                'profit': profit,
                'profit_asset': profit_asset,
                'status': status,
                'trade_type': trade_type,
                'buy_order_id': buy_order_id,
                'sell_order_id': sell_order_id,
                'executed_at': datetime.datetime.now()
            }
            
            # Add to the database first to get the ID
            try:
                async with async_session() as session:
                    trade = TradeHistory(
                        bot_id=bot_id,
                        buy_price=buy_price,
                        sell_price=sell_price,
                        quantity=quantity,
                        profit=profit,
                        profit_asset=profit_asset,
                        status=status,
                        trade_type=trade_type,
                        buy_order_id=buy_order_id,
                        sell_order_id=sell_order_id,
                        executed_at=datetime.datetime.now()
                    )
                    session.add(trade)
                    await session.commit()
                    await session.refresh(trade)  # Получаем обновленную запись с ID
                    
                    # Добавляем ID в trade_data
                    trade_data['id'] = trade.id
                    
                    # Add to local history with ID
                    self.trade_history.append(trade_data)
                    await self.trades_logger.debug(f"Added trade with ID {trade.id} to local history")
                    
                    return trade  # Возвращаем ID новой сделки
                    
            except Exception as e:
                await self.trades_logger.panic(f"Error adding trade to database: {e}")
                raise
                
        except Exception as e:
            await self.trades_logger.panic(f"Critical error in add_trade_to_history: {e}")
            raise

    async def add_active_order(self, bot_id, order_data):
        """Adds an active order to the database and local list."""
        try:
            # Create ActiveOrder object
            active_order = ActiveOrder(
                bot_id=bot_id,
                order_id=order_data["order_id"],
                order_type=order_data["order_type"],
                isInitial=order_data["isInitial"],
                price=float(order_data["price"]),
                quantity=float(order_data["quantity"]),
                created_at=datetime.datetime.now()
            )
            
            # Save to database
            async with async_session() as session:
                # Check if order exists
                existing_order = await session.execute(
                    select(ActiveOrder).where(ActiveOrder.order_id == active_order.order_id, 
                                              ActiveOrder.bot_id == bot_id)
                )
                if existing_order.scalar_one_or_none():
                    # If order exists, update it
                    await session.execute(
                        update(ActiveOrder)
                        .where(ActiveOrder.order_id == active_order.order_id, 
                               ActiveOrder.bot_id == bot_id)
                        .values(
                            order_type=active_order.order_type,
                            price=active_order.price,
                            quantity=active_order.quantity,
                            created_at=active_order.created_at
                        )
                    )
                else:
                    # If order doesn't exist, add new
                    session.add(active_order)
                
                await session.commit()
                
                # Update local list
                self.active_orders = [order for order in self.active_orders if order["order_id"] != active_order.order_id]
                self.active_orders.append({
                "order_id": active_order.order_id,
                "order_type": active_order.order_type,
                "price": active_order.price,
                "quantity": active_order.quantity,
                "created_at": str(active_order.created_at)
            })
            
            
        except Exception as e:
            await self.trades_logger.panic(f"Error saving active order: {e}")

    async def update_trade_in_history(self, bot_id, buy_price, sell_price, quantity, profit, profit_asset, status, trade_type):
        """Updates an existing trade in the history when it is closed."""
        async with async_session() as session:
            try:
                # Add ORDER BY executed_at DESC to get the latest trade
                result = await session.execute(
                    select(TradeHistory).where(
                        TradeHistory.buy_price == buy_price,
                        TradeHistory.quantity == quantity,
                        TradeHistory.status == 'OPEN',
                        TradeHistory.bot_id == bot_id
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
                            t['status'] == 'OPEN' and
                            t['bot_id'] == bot_id):
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
                    await self.trades_logger.panic(f"No open trade found with buy_price={buy_price}, quantity={quantity}, bot_id={bot_id}")
                    
            except Exception as e:
                await self.trades_logger.panic(f"Error updating trade history: {e}")
                await session.rollback()
                raise

    async def remove_active_order(self, bot_id, order_id):
        """Deletes an active order from the database and the local list."""
        try:
            # Delete from database
            async with async_session() as session:
                await session.execute(
                    delete(ActiveOrder).where(ActiveOrder.order_id == order_id, ActiveOrder.bot_id == bot_id)
                )
                await session.commit()
                
            # Delete from local list
            self.active_orders = [order for order in self.active_orders if order['order_id'] != order_id]
            await self.trades_logger.debug(f"Order {order_id} removed from active orders")
            
            # Delete from buy and sell positions
            self.buy_positions = [position for position in self.buy_positions if position['order_id'] != order_id]
            self.sell_positions = [position for position in self.sell_positions if position['order_id'] != order_id]
            
        except Exception as e:
            await self.trades_logger.panic(f"Error removing active order {order_id}: {e}")

    async def add_order_to_history(self, bot_id: int, order_id: str, order_type: str, isInitial: bool, price: float, quantity: float, status: str):
        """Adds a new order to the order history."""
        try:
            async with async_session() as session:
                order_history = OrderHistory(
                    bot_id=bot_id,
                    order_id=str(order_id),
                    order_type=order_type.lower(),
                    isInitial=isInitial,
                    price=price,
                    quantity=quantity,
                    status=status,
                    created_at=datetime.datetime.now()
                )
                session.add(order_history)
                await session.commit()
                await self.trades_logger.debug(f"Order {order_id} added to history")
        except Exception as e:
            await self.trades_logger.panic(f"Error adding order to history: {e}")
            raise

    async def update_order_history(self, bot_id: int, order_id: str, new_status: str):
        """Updates the status of an order in the order history."""
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(OrderHistory).where(OrderHistory.order_id == str(order_id), OrderHistory.bot_id == bot_id)
                )
                order = result.scalar_one_or_none()
                
                if order:
                    order.status = new_status
                    order.updated_at = datetime.datetime.now()
                    await session.commit()
                    await self.trades_logger.debug(f"Order {order_id} status updated to {new_status}")
                else:
                    await self.trades_logger.debug(f"Order {order_id} not found in history")
                    
        except Exception as e:
            await self.trades_logger.panic(f"Error updating order history: {e}")
            raise


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
        if self.current_price is None:
            self.trades_logger.log("current_price is None. Setting default value to 0.")
            current_price = 0
        else:
            current_price = self.current_price

        total_unrealized_profit_usdt = unrealized_profit_a + (unrealized_profit_b * current_price)

        result = {
            "unrealized_profit_a": unrealized_profit_a,
            "unrealized_profit_b": unrealized_profit_b,
            "total_unrealized_profit_usdt": total_unrealized_profit_usdt
        }
        
        return result


# ENDPOINTS

    async def get_strategy_status(self, bot_id: int):
        """Получает текущий статус стратегии для конкретного бота."""
        try:
            current_time = datetime.datetime.now()
            running_time = current_time - self.start_time if hasattr(self, 'start_time') else None
            total_profit_usdt = self.get_total_profit_usdt()
            unrealized_profit = self.calculate_unrealized_profit_loss()
            
            # Получаем активные ордера для конкретного бота
            async with async_session() as session:
                result = await session.execute(
                    select(ActiveOrder).where(ActiveOrder.bot_id == bot_id)
                )
                active_orders = result.scalars().all()
                active_orders_count = len(active_orders)
                
                # Получаем завершенные сделки для конкретного бота
                completed_trades_result = await session.execute(
                    select(TradeHistory).where(
                        TradeHistory.bot_id == bot_id,
                        TradeHistory.status == 'CLOSED'
                    )
                )
                completed_trades = completed_trades_result.scalars().all()
                completed_trades_count = len(completed_trades)
                
            # Получаем активные ордера из памяти только для этого бота
            bot_active_orders = [
                {
                    "order_id": order["order_id"],
                    "order_type": order["order_type"],
                    "price": order["price"],
                    "quantity": order["quantity"],
                    "created_at": order["created_at"]
                } 
                for order in self.active_orders 
                if order.get("bot_id") == bot_id
            ]

            return {
                "bot_id": bot_id,
                "status": "active" if not self.stop_flag else "inactive",
                "current_price": self.current_price,
                "initial_price": self.initial_price,
                "deviation": self.deviation,
                "realized_profit_a": self.realized_profit_a,
                "realized_profit_b": self.realized_profit_b,
                "total_profit_usdt": total_profit_usdt,
                "running_time": str(running_time) if running_time else None,
                "active_orders_count": active_orders_count,
                "completed_trades_count": completed_trades_count,
                "unrealized_profit": unrealized_profit,
                "active_orders": bot_active_orders,
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
        except Exception as e:
            logging.error(f"Error getting strategy status: {e}")
            raise

    async def stop_strategy(self):
        """Останавливает стратегию и очищает все ресурсы."""
        try:
            # Устанаввием флаг остановки
            self.stop_flag = True
        
            # Очищаем локальные списки
            self.active_orders = []
            self.buy_positions = []
            self.sell_positions = []
            self.open_trades = []
        
            # Очищаем таблицу активных ордеров в базе данных
            async with async_session() as session:
                await session.execute(delete(ActiveOrder).where(ActiveOrder.bot_id == self.bot_id))
                await session.commit()
            
            # Закрываем все сессии
            await self.close_all_sessions()
            
            await self.binance_client.cancel_all_orders_async(self.symbol)
            
            # Закрываем логгер
            await self.trades_logger.close()
        
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
            
            
            # Запуск основного цикла стратегии
            logging.info(f"Запуск стратегии для пары {self.symbol}")
            await self.execute_strategy()
            
            return True
        except Exception as e:
            logging.error(f"Ошибк при запуске стратегии: {e}")
            raise e

async def start_grid_strategy(parameters: dict) -> GridStrategy:
    """
    Создат и запускает экземпляр торговой стратегии.
    
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
        await strategy.close_all_sessions()
        await strategy.trades_logger.close()
        logging.info("Grid strategy stopped successfully")
        return True
    except Exception as e:
        logging.error(f"Ошибка при остановке grid-стратегии: {e}")
        raise


#tratata
