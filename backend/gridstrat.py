import asyncio
import logging
from binance_client import BinanceClient
import aiohttp
from asyncio_throttle import Throttler

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename='grid_trading.log')

class GridStrategy:
    def __init__(self, symbol, asset_a_funds, asset_b_funds, grids, deviation_threshold, trail_price=False, only_profitable_trades=False):
        self.symbol = symbol
        self.asset_a_funds = asset_a_funds
        self.asset_b_funds = asset_b_funds
        self.grids = grids
        self.deviation_threshold = deviation_threshold
        self.initial_price = None
        self.trail_price = trail_price
        self.grid_levels = []  # Store the calculated grid levels for buy and sell orders
        self.buy_positions = []  # Track individual buy positions (price and quantity)
        self.sell_positions = []  # Track individual sell positions (price and quantity)
        self.realized_profit_a = 0  # Track realized profit in Asset A (e.g., USDT)
        self.realized_profit_b = 0  # Track realized profit in Asset B (e.g., BTC)
        self.unrealized_profit_a = 0  # Track unrealized profit in Asset A
        self.unrealized_profit_b = 0  # Track unrealized profit in Asset B
        self.only_profitable_trades = only_profitable_trades  # Enable or disable only profitable trades mode
        self.order_size = 0
        self.binance_client = BinanceClient()
        self.session = aiohttp.ClientSession()
        self.throttler = Throttler(rate_limit=5, period=1)  # Throttle to 5 requests per second

    async def calculate_order_size(self):
        """Calculate the order size based on allocated funds for each grid level."""
        self.buy_order_size = self.asset_a_funds / self.grids  # USDT allocated to each buy level
        self.sell_order_size = self.asset_b_funds / self.grids  # BTC allocated to each sell level
        logging.info(f"Calculated buy order size: {self.buy_order_size}, sell order size: {self.sell_order_size}")

    async def calculate_grid_levels(self, current_price):
        """Calculate grid levels based on current price and deviation threshold."""
        step_distance = (self.deviation_threshold / self.grids) * current_price
        # Calculate buy levels (below current price) and sell levels (above current price)
        self.grid_levels = {
            'buy': [current_price - (i * step_distance) for i in range(1, self.grids + 1)],
            'sell': [current_price + (i * step_distance) for i in range(1, self.grids + 1)]
        }
        logging.info(f"Calculated grid levels: Buy levels: {self.grid_levels['buy']}, Sell levels: {self.grid_levels['sell']}")

    async def place_batch_orders(self):
        """Place initial buy and sell orders based on grid levels in batches."""
        batch_size = 5  # Place orders in batches of 5 to avoid hitting rate limits
        logging.info("Placing batch orders...")
        for order_type, levels in self.grid_levels.items():
            tasks = []
            for i in range(0, len(levels), batch_size):
                for level in levels[i:i + batch_size]:
                    # Create a task to place each limit order
                    tasks.append(self.place_limit_order(level, order_type))
            # Execute all the tasks concurrently
            await asyncio.gather(*tasks)
            await asyncio.sleep(2)  # Pause between batches to avoid rate limits
        logging.info("Batch orders placed.")

    async def place_limit_order(self, level, order_type, order_size):
        """Place an individual limit order and log the outcome."""
        async with self.throttler:
            try:
                price = level
                # Place a limit order asynchronously using the Binance client
                logging.info(f"Attempting to place {order_type} order at level {level:.2f} for {order_size} units.")
                order = await self.binance_client.place_order_async(self.symbol, order_type, order_size, price)
                
                if order:
                    message = f"Placed {order_type} limit order at level {level:.2f} for {order_size} units."
                    logging.info(message)
                    print(message)
                else:
                    logging.warning(f"Failed to place {order_type} order at level {level:.2f}")
            except Exception as e:
                logging.error(f"Error placing {order_type} order at level {level:.2f}: {str(e)}")

    async def execute_strategy(self):
        """Execute the grid trading strategy with continuous monitoring."""
        while True:
            try:
                # Fetch the current price from the Binance client
                current_price = await self.binance_client.get_current_price_async(self.symbol)
                if current_price:
                    # Initialize the initial price and place grid orders
                    if self.initial_price is None:
                        self.initial_price = current_price
                        logging.info(f"Initial price set to: {self.initial_price}")
                        await self.calculate_order_size()
                        await self.calculate_grid_levels(self.initial_price)
                        await self.place_batch_orders()

                    # Calculate the deviation from the initial price
                    deviation = (current_price - self.initial_price) / self.initial_price

                    # Log the current price and deviation
                    logging.info(f"Current price: {current_price:.2f}, Current deviation: {deviation:.2%}")

                    # Check if the current price matches any buy or sell level and place an opposite order
                    if current_price in self.grid_levels['buy']:
                        logging.info(f"Buy level reached at price: {current_price:.2f}")
                        # Buy order filled, evaluate profitability for placing a corresponding sell order
                        if self.only_profitable_trades:
                            # Check if the current price allows for a profitable sell
                            profitable_sell = any(current_price > buy['price'] for buy in self.buy_positions)
                            if not profitable_sell:
                                logging.info(f"Skipping sell order at {current_price} as it is not profitable.")
                                continue
                        # Place a new sell order above the current price
                        new_sell_level = current_price + ((self.deviation_threshold / self.grids) * self.initial_price)
                        self.grid_levels['sell'].append(new_sell_level)
                        await self.place_limit_order(new_sell_level, 'SELL', self.sell_order_size)
                        # Track the sell position
                        self.sell_positions.append({'price': new_sell_level, 'quantity': self.sell_order_size})
                        # Adjust available funds for Asset B
                        self.asset_b_funds -= self.sell_order_size
                        # Remove the filled buy level from grid levels
                        self.grid_levels['buy'].remove(current_price)
                    elif current_price in self.grid_levels['sell']:
                        logging.info(f"Sell level reached at price: {current_price:.2f}")
                        # Sell order filled, evaluate profitability for placing a corresponding buy order
                        if self.only_profitable_trades:
                            # Check if the current price allows for a profitable buy
                            profitable_buy = any(current_price < sell['price'] for sell in self.sell_positions)
                            if not profitable_buy:
                                logging.info(f"Skipping buy order at {current_price} as it is not profitable.")
                                continue
                        # Place a new buy order below the current price
                        new_buy_level = current_price - ((self.deviation_threshold / self.grids) * self.initial_price)
                        self.grid_levels['buy'].append(new_buy_level)
                        await self.place_limit_order(new_buy_level, 'BUY', self.buy_order_size)
                        # Track the buy position
                        self.buy_positions.append({'price': new_buy_level, 'quantity': self.buy_order_size})
                        # Adjust available funds for Asset A
                        self.asset_a_funds -= new_buy_level * self.buy_order_size
                        # Remove the filled sell level from grid levels
                        self.grid_levels['sell'].remove(current_price)

                    # Reset grid if deviation threshold is reached
                    elif abs(deviation) >= self.deviation_threshold:
                        logging.info("Deviation threshold reached. Resetting grid.")
                        # Carry forward weighted average and positions after reset
                        self.buy_positions = [{'price': buy['price'], 'quantity': buy['quantity']} for buy in self.buy_positions]
                        self.sell_positions = [{'price': sell['price'], 'quantity': sell['quantity']} for sell in self.sell_positions]
                        # Cancel all open orders and reset the grid
                        await self.cancel_all_orders()
                        await self.reset_grid(current_price)

                # Sleep asynchronously to wait before the next price check
                await asyncio.sleep(5)  # Check every 5 seconds

            except Exception as e:
                logging.error(f"Error in strategy execution: {str(e)}")

    async def reset_grid(self, new_initial_price):
        """Reset the grid when the deviation threshold is reached."""
        logging.info("Resetting grid levels.")
        self.initial_price = new_initial_price  # Update the initial price
        await self.calculate_grid_levels(self.initial_price)  # Recalculate grid levels based on the new price
        await self.place_batch_orders()  # Place new orders after resetting the grid

    async def cancel_all_orders(self):
        """Cancel all open orders."""
        async with self.throttler:
            try:
                # Cancel all open orders using the Binance client
                logging.info("Attempting to cancel all open orders...")
                cancelled_orders = await self.binance_client.cancel_all_orders_async(self.symbol)
                if cancelled_orders:
                    logging.info(f"Cancelled all open orders for {self.symbol}.")
                else:
                    logging.warning(f"No open orders to cancel for {self.symbol}.")
            except Exception as e:
                logging.error(f"Error cancelling orders: {str(e)}")

    async def close(self):
        """Close any open sessions."""
        logging.info("Closing session.")
        await self.session.close()  # Close the HTTP session

async def main():
    # Define trading parameters
    symbol = "BTCUSDT"
    asset_a_funds = 1000