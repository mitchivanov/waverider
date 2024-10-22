import asyncio
import logging
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from binance_client import BinanceClient
from root import settings
import aiohttp
from asyncio_throttle import Throttler
from binance_websocket import BinanceWebSocket  # Import the WebSocket class
import os
import decimal
import time  # Import the time module

# Configure logging for the entire application
logging.basicConfig(
    level=logging.INFO,  # Set the default logging level to INFO
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='grid_trading.log'
)

# Suppress debug messages from the websockets library
logging.getLogger('websockets').setLevel(logging.WARNING)

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
        only_profitable_trades=False
    ):
        # Securely retrieve API credentials from environment variables
        api_key = os.getenv('BINANCE_API_KEY')
        api_secret = os.getenv('BINANCE_API_SECRET')

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
        self.session = aiohttp.ClientSession
        self.throttler = Throttler(rate_limit=5, period=1)
        self.current_price = None  # Initialize current price
        self.websocket = BinanceWebSocket(self.symbol)  # Initialize the WebSocket
        self.stop_flag = False  # Initialize the stop flag
        self.active_orders = []  # List to store active orders
        self.trade_history = []  # List to store completed trades
        self.growth_factor = growth_factor  # Store the growth factor
        self.use_granular_distribution = use_granular_distribution  # Store the flag for granular distribution

        # Check account balance
        self.check_account_balance()

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

    async def send_update(self, update_info):
        """Send an update about the order status."""
        # Example implementation: log the update
        logging.info(f"Update: {update_info}")

    async def place_limit_order(self, price, order_type, order_size):
        """Place an individual limit order and log the outcome."""
        logging.info(f"Placing {order_type.upper()} order at ${price} for {order_size} units.")
        async with self.throttler:
            try:
                # Perform a balance check before placing the order
                if not self.is_balance_sufficient(order_type, price, order_size):
                    logging.error(f"Insufficient balance to place {order_type.upper()} order at ${price} for {order_size} units.")
                    return

                # Retrieve exchange info
                exchange_info = self.binance_client.client.get_symbol_info(self.symbol)
                if exchange_info is None:
                    logging.error(f"Exchange information for symbol {self.symbol} not found.")
                    return

                # Extract filters
                filters = self.extract_filters(exchange_info)
                if filters is None:
                    logging.error(f"Could not extract filters for symbol {self.symbol}.")
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
                    logging.error(f"Price {price} is outside the allowed range ({min_price} - {max_price}).")
                    return

                # Ensure quantity is within min and max quantity
                if order_size < min_qty or order_size > max_qty:
                    logging.error(f"Quantity {order_size} is outside the allowed range ({min_qty} - {max_qty}).")
                    return

                # Ensure order notional is within min and max notional
                notional = price * order_size
                if notional < min_notional or notional > max_notional:
                    logging.error(f"Order notional ({notional}) is outside the allowed range ({min_notional} - {max_notional}).")
                    return

                # Log and place the order
                # logging.info(f"Attempting to place a single {order_type.upper()} order at ${price} for {order_size} units.")
                order = await self.binance_client.place_order_async(
                    self.symbol, order_type.upper(), order_size, price
                )
                # logging.debug("Order placed, checking response...")

                # Remove or comment out these debug logs
                # logging.debug(f"Params: {params}")
                # logging.debug(f"Headers: {headers}")
                # logging.info(f"Order response: {order}")
                # Check if the order was successful and log the result
                if 'orderId' in order:
                    # message = f"Successfully placed {order_type.upper()} limit order at ${price} for {order_size} units."
                    # logging.info(message)
                    # Update positions and active orders
                    if order_type.lower() == 'buy':
                        self.buy_positions.append({'price': price, 'quantity': order_size})
                    elif order_type.lower() == 'sell':
                        self.sell_positions.append({'price': price, 'quantity': order_size})

                    order_id = order['orderId']
                    self.active_orders.append({
                        'order_id': order_id,
                        'order_type': order_type,
                        'price': price,
                        'quantity': order_size
                    })
                    await self.send_update({
                        'event': 'order_placed',
                        'order_type': order_type,
                        'price': price,
                        'order_size': order_size,
                    })
                else:
                    # Handle API error response
                    error_code = order.get('code')
                    error_msg = order.get('msg')
                    logging.error(f"Failed to place order: {error_code} - {error_msg}")
            except Exception as e:
                logging.error(f"Error placing {order_type.upper()} order at ${price}: {str(e)}")

    async def place_batch_orders(self):
        """Place initial buy and sell orders based on grid levels in batches."""
        batch_size = 5  # Place orders in batches to avoid hitting rate limits
        logging.info("Starting to place batch orders for initial grid levels.")

        for order_type in ['buy', 'sell']:
            levels = self.grid_levels[order_type]
            order_sizes = self.buy_order_sizes if order_type == 'buy' else self.sell_order_sizes
            total_orders = len(levels)
            successful_orders = 0
            failed_orders = 0

            # Debug logging for order sizes and total orders
            logging.debug(f"Order type: {order_type}")
            logging.debug(f"Total orders: {total_orders}")
            logging.debug(f"Buy order sizes: {self.buy_order_sizes}")
            logging.debug(f"Sell order sizes: {self.sell_order_sizes}")
            logging.debug(f"Current order sizes: {order_sizes}")

            for i in range(0, total_orders, batch_size):
                batch_levels = levels[i:i + batch_size]
                batch_sizes = order_sizes[i:i + batch_size]
                logging.info(
                    f"Attempting to place batch of {len(batch_levels)} {order_type.upper()} orders for levels: {batch_levels[0]:.2f} to {batch_levels[-1]:.2f}"
                )
                tasks = []
                logging.debug(f"Entering for loop with batch_levels: {batch_levels} and batch_sizes: {batch_sizes}")
                for level_price, order_size in zip(batch_levels, batch_sizes):
                    logging.debug(f"Processing level_price: {level_price}, order_size: {order_size}")
                    # Create a task to place each limit order
                    task = self.place_limit_order(level_price, order_type, order_size)
                    tasks.append(task)
                    logging.info(f"Placing order at ${level_price:.2f} for {order_size} units.")
                    logging.debug(f"Task appended: {task}")
                logging.debug(f"Exiting for loop. Total tasks: {len(tasks)}")
                # Execute all the tasks concurrently
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Count successful and failed orders
                for result in results:
                    if isinstance(result, Exception):
                        failed_orders += 1
                    else:
                        successful_orders += 1

                logging.info(
                    f"Placed {order_type.upper()} orders for levels: {batch_levels[0]:.2f} to {batch_levels[-1]:.2f}."
                )
                logging.info(
                    f"Successful orders: {successful_orders}, Failed orders: {failed_orders}"
                )
                logging.info(
                    f"Total orders: {total_orders}, Remaining orders: {total_orders - (successful_orders + failed_orders)}"
                )
                await asyncio.sleep(2)  # Pause between batches to avoid rate limits
        logging.info("All batch orders have been placed successfully.")

    async def execute_strategy(self):
        """Execute the grid trading strategy with continuous monitoring."""
        logging.info("Starting the grid trading strategy execution.")

        # Start the WebSocket in a separate task to continuously update the price
        price_update_task = asyncio.create_task(self.update_price())

        last_checked_price = None  # Track the last checked price

        try:
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
                        
                        # Place initial batch orders
                        await self.place_batch_orders()

                    # Calculate the deviation from the initial price
                    deviation = (self.current_price - self.initial_price) / self.initial_price

                    # Log the current price and deviation
                    logging.info(f"Current price: ${self.current_price:.2f}. Deviation: {deviation:.2%}.")

                    # Define tasks for checking buy and sell orders
                    async def check_buy_orders():
                        buy_prices = [buy['price'] for buy in self.buy_positions]
                        logging.info(f"Checking {len(self.buy_positions)} buy orders at prices: {buy_prices}")
                        for buy in list(self.buy_positions):
                            if self.current_price <= buy['price']:
                                logging.info(f"Buy order triggered at price ${buy['price']:.2f}")
                                sell_price = buy['price'] + ((self.deviation_threshold / self.grids) * self.initial_price)
                                await self.place_limit_order(sell_price, 'sell', buy['quantity'])
                                self.buy_positions.remove(buy)
                                profit = (sell_price - buy['price']) * buy['quantity']
                                self.realized_profit_a += profit
                                logging.info(f"Realized profit from buy-sell pair: ${profit:.2f}")
                                self.trade_history.append({
                                    'buy_price': buy['price'],
                                    'sell_price': sell_price,
                                    'quantity': buy['quantity'],
                                    'profit': profit
                                })

                    async def check_sell_orders():
                        sell_prices = [sell['price'] for sell in self.sell_positions]
                        logging.info(f"Checking {len(self.sell_positions)} sell orders at prices: {sell_prices}")
                        for sell in list(self.sell_positions):
                            if self.current_price >= sell['price']:
                                logging.info(f"Sell order triggered at price ${sell['price']:.2f}")
                                buy_price = sell['price'] - ((self.deviation_threshold / self.grids) * self.initial_price)
                                await self.place_limit_order(buy_price, 'buy', sell['quantity'])
                                self.sell_positions.remove(sell)
                                profit = (sell['price'] - buy_price) * sell['quantity']
                                self.realized_profit_b += profit
                                logging.info(f"Realized profit from sell-buy pair: ${profit:.2f}")
                                self.trade_history.append({
                                    'sell_price': sell['price'],
                                    'buy_price': buy_price,
                                    'quantity': sell['quantity'],
                                    'profit': profit
                                })

                    # Run both checks concurrently
                    await asyncio.gather(check_buy_orders(), check_sell_orders())

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
            await price_update_task
            await self.close()

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
                # Cancel all open orders using the Binance client
                cancelled_orders = await self.binance_client.cancel_all_orders_async(
                    self.symbol
                )
                if cancelled_orders:
                    logging.info(f"All open orders for {self.symbol} have been cancelled.")
                else:
                    logging.warning(f"No open orders to cancel for {self.symbol}.")
            except Exception as e:
                logging.error(f"Error cancelling orders: {str(e)}")

    async def close(self):
        """Close any open sessions."""
        logging.info("Closing the trading session.")
        await self.session.close()  # Close the HTTP session
        await self.websocket.stop()  # Stop the WebSocket connection

    def stop(self):
        """Set the stop flag to true to stop the strategy execution."""
        logging.info("Stopping the grid trading strategy.")
        self.stop_flag = True

    def get_active_orders(self):
        """Return a list of currently active orders."""
        return [
            {"id": 1, "order_type": "buy", "price": 50000, "quantity": 0.1},
            {"id": 2, "order_type": "sell", "price": 51000, "quantity": 0.1},
        ]

    def get_trade_history(self):
        """Return a list of completed trades."""
        return self.trade_history

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
        account_info = self.binance_client.client.get_account()
        balances = {balance['asset']: float(balance['free']) for balance in account_info['balances']}

        # Extract base and quote assets from the symbol
        base_asset = self.symbol.replace('USDT', '')  # For symbols ending with USDT
        quote_asset = 'USDT'

        if order_type.lower() == 'buy':
            required_funds = price * quantity  # Total cost in quote asset
            available_funds = balances.get(quote_asset, 0)
            if available_funds < required_funds:
                logging.error(f"Insufficient {quote_asset} balance. Required: {required_funds}, Available: {available_funds}")
                return False
        elif order_type.lower() == 'sell':
            required_quantity = quantity  # Quantity in base asset
            available_quantity = balances.get(base_asset, 0)
            if available_quantity < required_quantity:
                logging.error(f"Insufficient {base_asset} balance. Required: {required_quantity}, Available: {available_quantity}")
                return False
        return True


























