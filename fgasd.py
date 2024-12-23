import asyncio
import logging
import datetime
import os
import numpy as np
import itertools
import time
from typing import List, Dict, Optional

from binance.client import AsyncClient
from binance.exceptions import BinanceAPIException, BinanceOrderException
from binance import BinanceSocketManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='index_fund.log'
)

# Add a stream handler for console output
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(console_handler)

class IndexFundCalculator:
    def __init__(
        self,
        assets: List[str],
        target_weights: List[float],
        total_funds: Optional[float],
        asset_funds: Optional[Dict[str, float]],
        num_levels: int = 4,
        orders_per_level: int = 3,
        use_bollinger_bands: bool = False,
        use_pairwise_trading: bool = False,
        increased_risk: bool = False,
        use_weighted_orders: bool = False,
        pairwise_trade_fraction: float = 0.005  # Fraction for incremental adjustments (e.g., 0.5%)
    ):
        # Validate inputs
        if len(assets) != len(target_weights):
            raise ValueError("Assets and target_weights must have the same length.")
        if not abs(sum(target_weights) - 1.0) < 1e-6:
            raise ValueError("Target weights must sum to 1.")
        if total_funds is None and asset_funds is None:
            raise ValueError("Either total_funds or asset_funds must be provided.")

        self.api_key = '55euYhdLmx17qhTB1KhBSbrsS3A79bYU0C408VHMYsTTMcsyfSMboJ1d1uEWNLq3'
        self.api_secret = 'BINANCE_API_SECRET', '2zlWvVVQIrj5ZryMNCkt9KIqowlQQMdG0bcV4g4LAinOnF8lc7O3Udumn6rIAyLb'
        self.assets = assets
        self.target_weights = target_weights
        self.total_funds = total_funds
        self.asset_funds = asset_funds
        self.num_levels = num_levels
        self.orders_per_level = orders_per_level
        self.level_threshold = float(input("Enter the total deviation threshold to trigger rebalancing (e.g., 0.02 for 2%): "))
        self.use_bollinger_bands = use_bollinger_bands
        self.use_pairwise_trading = use_pairwise_trading
        self.increased_risk = increased_risk
        self.use_weighted_orders = use_weighted_orders  # Use weighted orders
        self.pairwise_trade_fraction = pairwise_trade_fraction  # Fraction for incremental adjustments

        self.bollinger_cooldown = 600  # Cooldown period in seconds (e.g., 10 minutes)
        self.bollinger_last_triggered: Dict[str, float] = {asset: 0.0 for asset in assets}

        # Portfolio and order initialization
        self.portfolio: Dict[str, float] = {asset: 0.0 for asset in assets}
        self.current_prices: Dict[str, float] = {asset: 0.0 for asset in assets}
        self.price_history: Dict[str, List[float]] = {asset: [] for asset in assets}
        self.orders: Dict[str, Dict] = {}  # Tracking active orders by order ID
        self.historical_data_cache: Dict[str, Dict] = {}  # Cache for historical prices

        self.stop_flag = False

        # Initialize Binance client
        self.client = None

    def calculate_bollinger_bands(self, prices: List[float], window_size: int = 20, num_std_dev: int = 2):
        """Calculate Bollinger Bands for a given list of prices."""
        if len(prices) < window_size:
            window_size = len(prices)
        moving_average = np.mean(prices[-window_size:])
        std_deviation = np.std(prices[-window_size:])
        upper_band = moving_average + (num_std_dev * std_deviation)
        lower_band = moving_average - (num_std_dev * std_deviation)
        return lower_band, upper_band

    async def websocket_price_updates(self):
        """Subscribe to price updates and accumulate price history."""
        try:
            bm = BinanceSocketManager(self.client)
            streams = [f"{asset.lower()}usdt@miniTicker" for asset in self.assets]
            ts = bm.multiplex_socket(streams)
            async with ts as tscm:
                while not self.stop_flag:
                    res = await tscm.recv()
                    data = res['data']
                    symbol = data['s'][:-4]  # Remove 'USDT' from symbol
                    price = float(data['c'])
                    self.current_prices[symbol] = price
                    self.price_history[symbol].append(price)
                    # Limit the price history to last N prices
                    max_prices = 100  # Adjust as needed
                    if len(self.price_history[symbol]) > max_prices:
                        self.price_history[symbol].pop(0)
                    logging.info(f"Updated price for {symbol}: {price:.2f}")
                    await self.monitor_and_rebalance()
        except Exception as e:
            logging.error(f"WebSocket error: {e}")
            # Reconnect after a delay
            if not self.stop_flag:
                await asyncio.sleep(5)
                await self.websocket_price_updates()

    async def monitor_and_rebalance(self):
        """Monitor the portfolio and place orders as deviations occur."""
        # Cancel existing open orders before rebalancing
        await self.cancel_open_orders()

        # Calculate total portfolio value
        total_value = sum(self.portfolio[asset] * self.current_prices[asset] for asset in self.assets)
        if total_value == 0 and self.total_funds is not None:
            total_value = self.total_funds

        # Debug logging for portfolio composition
        logging.info("Current Portfolio Status:")
        logging.info(f"Total Portfolio Value: ${total_value:.2f} USDT")
        for asset in self.assets:
            current_value = self.portfolio[asset] * self.current_prices[asset]
            current_weight = current_value / total_value if total_value > 0 else 0
            target_weight = self.target_weights[self.assets.index(asset)]
            logging.info(f"{asset}:")
            logging.info(f"  Amount: {self.portfolio[asset]:.8f}")
            logging.info(f"  Value: ${current_value:.2f}")
            logging.info(f"  Current Weight: {current_weight:.2%}")
            logging.info(f"  Target Weight: {target_weight:.2%}")
            logging.info(f"  Deviation: {(current_weight - target_weight):.2%}")

        # Calculate current deviations
        deviations = self.calculate_deviations(total_value)

        # Place orders based on deviations
        for asset, deviation in deviations.items():
            if abs(deviation) >= self.level_threshold:
                await self.place_proportional_orders(asset, deviation, total_value)

        # Pairwise trading if enabled
        if self.use_pairwise_trading:
            await self.place_pairwise_orders()

    def calculate_deviations(self, total_value: float) -> Dict[str, float]:
        """Calculate deviations from target weights."""
        deviations = {}
        for asset, target_weight in zip(self.assets, self.target_weights):
            current_value = self.portfolio[asset] * self.current_prices[asset]
            current_weight = current_value / total_value if total_value > 0 else 0
            deviation = target_weight - current_weight  # Target - Current
            deviations[asset] = deviation
        return deviations

    async def place_proportional_orders(self, asset: str, deviation: float, total_value: float):
        """Place multiple proportional limit orders based on the deviation."""
        direction = 'buy' if deviation > 0 else 'sell'
        # Calculate the total order amount in USDT
        total_order_amount_usdt = abs(deviation) * total_value
        if self.increased_risk:
            total_order_amount_usdt *= 1.5  # Increase order size for higher risk

        # Adjust order amount based on Bollinger Bands if enabled and cooldown has passed
        current_time = time.time()
        if self.use_bollinger_bands:
            last_triggered = self.bollinger_last_triggered.get(asset, 0)
            if current_time - last_triggered >= self.bollinger_cooldown:
                lower_band, upper_band = self.calculate_bollinger_bands(self.price_history[asset])
                current_price = self.current_prices[asset]
                if direction == 'buy' and current_price < lower_band:
                    total_order_amount_usdt *= 1.2
                    self.bollinger_last_triggered[asset] = current_time
                    logging.info(f"{asset} price is below lower Bollinger Band. Increasing buy order size.")
                elif direction == 'sell' and current_price > upper_band:
                    total_order_amount_usdt *= 1.2
                    self.bollinger_last_triggered[asset] = current_time
                    logging.info(f"{asset} price is above upper Bollinger Band. Increasing sell order size.")

        # Split the total order amount into multiple orders for granularity
        num_orders = self.num_levels * self.orders_per_level

        # Generate limit prices with more orders closer to the current price
        limit_prices = self.generate_limit_prices(asset, direction, num_orders)

        # Reverse weighting: Larger orders further from current price
        order_amounts_usdt = self.calculate_order_weights(total_order_amount_usdt, num_orders)

        # Adjust order sizes based on limit prices to consider price impact
        price = self.current_prices[asset]
        adjusted_order_amounts = []
        for amount_usdt, limit_price in zip(order_amounts_usdt, limit_prices):
            adjusted_amount_usdt = amount_usdt * (price / limit_price)
            adjusted_order_amounts.append(adjusted_amount_usdt)

        # Place limit orders
        for amount_usdt, limit_price in zip(adjusted_order_amounts, limit_prices):
            order_size = amount_usdt / limit_price  # Convert USDT amount to asset amount
            logging.info(f"Placing {direction.upper()} LIMIT order for {asset}: {order_size:.6f} at price {limit_price:.6f} USDT")

            order_id = await self.place_limit_order(
                price=limit_price,
                order_type=direction,
                order_size=order_size,
                asset=asset
            )

            if order_id:
                self.orders[order_id] = {
                    "id": order_id,
                    "asset": asset,
                    "order_type": direction,
                    "order_size": order_size,
                    "status": "open",
                    "price": limit_price
                }

    def generate_limit_prices(self, asset: str, direction: str, num_orders: int) -> List[float]:
        """Generate limit prices with more orders closer to the current price."""
        price = self.current_prices[asset]
        limit_prices = []
        max_offset = self.level_threshold
        min_offset = 0.0001  # Minimal offset to avoid placing at the current price
        for level in range(1, self.num_levels + 1):
            for order_num in range(1, self.orders_per_level + 1):
                # Calculate a non-linear offset to have more orders near the current price
                if direction == 'buy':
                    offset = min_offset + (np.log(order_num + (level - 1) * self.orders_per_level) / np.log(num_orders + 1)) * max_offset
                    limit_price = price * (1 - offset)
                else:
                    offset = min_offset + (np.log(order_num + (level - 1) * self.orders_per_level) / np.log(num_orders + 1)) * max_offset
                    limit_price = price * (1 + offset)
                limit_prices.append(limit_price)
        return limit_prices

    def calculate_order_weights(self, total_order_amount_usdt: float, num_orders: int) -> List[float]:
        """Calculate order weights based on the weighting scheme."""
        if self.use_weighted_orders:
            # Assign larger weights to orders further away
            weights = np.linspace(1, 0.1, num_orders)
            weights /= weights.sum()  # Normalize weights
            order_amounts_usdt = total_order_amount_usdt * weights
        else:
            # Evenly distribute the order amounts
            order_amounts_usdt = [total_order_amount_usdt / num_orders] * num_orders
        return order_amounts_usdt

    async def place_pairwise_orders(self):
        """Place orders between asset pairs based on their price ratios."""
        for asset_1, asset_2 in itertools.combinations(self.assets, 2):
            if len(self.price_history[asset_1]) < 20 or len(self.price_history[asset_2]) < 20:
                continue  # Not enough data yet
            ratio = self.current_prices[asset_1] / self.current_prices[asset_2]
            ratios = [p1 / p2 for p1, p2 in zip(self.price_history[asset_1][-20:], self.price_history[asset_2][-20:])]
            lower_band, upper_band = self.calculate_bollinger_bands(ratios)

            # Check the impact on portfolio balance
            total_value = sum(self.portfolio[asset] * self.current_prices[asset] for asset in self.assets)
            deviation_asset_1 = self.target_weights[self.assets.index(asset_1)] - (self.portfolio[asset_1] * self.current_prices[asset_1]) / total_value
            deviation_asset_2 = self.target_weights[self.assets.index(asset_2)] - (self.portfolio[asset_2] * self.current_prices[asset_2]) / total_value

            if ratio < lower_band and deviation_asset_1 > 0 and deviation_asset_2 < 0:
                logging.info(f"{asset_1} is undervalued compared to {asset_2}. Considering buying {asset_1} with {asset_2}.")
                await self.cross_pair_trade(asset_1, asset_2, 'buy')
            elif ratio > upper_band and deviation_asset_1 < 0 and deviation_asset_2 > 0:
                logging.info(f"{asset_1} is overvalued compared to {asset_2}. Considering selling {asset_1} for {asset_2}.")
                await self.cross_pair_trade(asset_1, asset_2, 'sell')

    async def cross_pair_trade(self, asset_1, asset_2, action):
        """Trade between two assets to bring portfolio closer to target allocations."""
        # Debug logging before simulation
        logging.info(f"\nSimulating {action.upper()} trade between {asset_1} and {asset_2}")
        logging.info("Before Trade:")
        total_value = sum(self.portfolio[asset] * self.current_prices[asset] for asset in self.assets)
        for asset in [asset_1, asset_2]:
            current_weight = (self.portfolio[asset] * self.current_prices[asset]) / total_value
            target_weight = self.target_weights[self.assets.index(asset)]
            logging.info(f"{asset}:")
            logging.info(f"  Balance: {self.portfolio[asset]:.8f}")
            logging.info(f"  Current Weight: {current_weight:.2%}")
            logging.info(f"  Target Weight: {target_weight:.2%}")

        # Use incremental adjustments
        amount_asset_1 = self.portfolio[asset_1] * self.pairwise_trade_fraction
        amount_asset_2 = self.portfolio[asset_2] * self.pairwise_trade_fraction

        if amount_asset_1 <= 0 or amount_asset_2 <= 0:
            return

        # Simulate portfolio after trade
        simulated_portfolio = self.portfolio.copy()

        if action == 'sell':
            # Simulate selling asset_1 for asset_2
            simulated_portfolio[asset_1] -= amount_asset_1
            simulated_portfolio[asset_2] += amount_asset_1 * (self.current_prices[asset_1] / self.current_prices[asset_2])
        elif action == 'buy':
            # Simulate selling asset_2 for asset_1
            simulated_portfolio[asset_2] -= amount_asset_2
            simulated_portfolio[asset_1] += amount_asset_2 * (self.current_prices[asset_2] / self.current_prices[asset_1])

        # Recalculate deviations
        total_value = sum(simulated_portfolio[asset] * self.current_prices[asset] for asset in self.assets)
        simulated_deviations = self.calculate_deviations_for_portfolio(simulated_portfolio, total_value)

        # Calculate total deviation before and after trade
        current_deviations = self.calculate_deviations(total_value)
        total_current_deviation = sum(abs(dev) for dev in current_deviations.values())
        total_simulated_deviation = sum(abs(dev) for dev in simulated_deviations.values())

        # Proceed only if the trade reduces the total deviation
        if True:
            # Check for direct trading pair
            direct_pair = f"{asset_1}{asset_2}"
            inverse_pair = f"{asset_2}{asset_1}"
            symbol_info_direct = await self.client.get_symbol_info(direct_pair)
            symbol_info_inverse = await self.client.get_symbol_info(inverse_pair)

            if symbol_info_direct is not None:
                # Direct pair exists (asset_1/asset_2)
                logging.info(f"Executing direct trade: {direct_pair}")
                if action == 'sell':
                    # Sell asset_1 for asset_2
                    await self.place_limit_order(
                        price=self.current_prices[asset_1] / self.current_prices[asset_2],
                        order_type='sell',
                        order_size=amount_asset_1,
                        asset=asset_1,
                        quote_asset=asset_2
                    )
                    # Update portfolio
                    await self.update_portfolio_after_trade(asset_1, amount_asset_1, 'sell')
                    amount_asset_2_received = amount_asset_1 * (self.current_prices[asset_1] / self.current_prices[asset_2])
                    await self.update_portfolio_after_trade(asset_2, amount_asset_2_received, 'buy')
                elif action == 'buy':
                    # Buy asset_1 with asset_2
                    await self.place_limit_order(
                        price=self.current_prices[asset_1] / self.current_prices[asset_2],
                        order_type='buy',
                        order_size=amount_asset_1,
                        asset=asset_1,
                        quote_asset=asset_2
                    )
                    # Update portfolio
                    await self.update_portfolio_after_trade(asset_2, amount_asset_2, 'sell')
                    amount_asset_1_received = amount_asset_2 * (self.current_prices[asset_2] / self.current_prices[asset_1])
                    await self.update_portfolio_after_trade(asset_1, amount_asset_1_received, 'buy')
            elif symbol_info_inverse is not None:
                # Inverse pair exists (asset_2/asset_1)
                logging.info(f"Executing inverse trade: {inverse_pair}")
                if action == 'sell':
                    # Buy asset_2 with asset_1
                    await self.place_limit_order(
                        price=self.current_prices[asset_2] / self.current_prices[asset_1],
                        order_type='buy',
                        order_size=amount_asset_2,
                        asset=asset_2,
                        quote_asset=asset_1
                    )
                    # Update portfolio
                    await self.update_portfolio_after_trade(asset_1, amount_asset_1, 'sell')
                    amount_asset_2_received = amount_asset_1 * (self.current_prices[asset_1] / self.current_prices[asset_2])
                    await self.update_portfolio_after_trade(asset_2, amount_asset_2_received, 'buy')
                elif action == 'buy':
                    # Sell asset_2 for asset_1
                    await self.place_limit_order(
                        price=self.current_prices[asset_2] / self.current_prices[asset_1],
                        order_type='sell',
                        order_size=amount_asset_2,
                        asset=asset_2,
                        quote_asset=asset_1
                    )
                    # Update portfolio
                    await self.update_portfolio_after_trade(asset_2, amount_asset_2, 'sell')
                    amount_asset_1_received = amount_asset_2 * (self.current_prices[asset_2] / self.current_prices[asset_1])
                    await self.update_portfolio_after_trade(asset_1, amount_asset_1_received, 'buy')
            else:
                # No direct pair exists, use USDT as intermediate
                logging.info(f"No direct pair between {asset_1} and {asset_2}. Using USDT as intermediate.")
                if action == 'sell':
                    # Sell asset_1 for USDT, then buy asset_2 with USDT
                    order_id_sell = await self.place_limit_order(
                        price=self.current_prices[asset_1],
                        order_type='sell',
                        order_size=amount_asset_1,
                        asset=asset_1
                    )
                    usdt_amount = amount_asset_1 * self.current_prices[asset_1]
                    order_size_buy = usdt_amount / self.current_prices[asset_2]
                    order_id_buy = await self.place_limit_order(
                        price=self.current_prices[asset_2],
                        order_type='buy',
                        order_size=order_size_buy,
                        asset=asset_2
                    )
                    if order_id_sell and order_id_buy:
                        # Update portfolio
                        await self.update_portfolio_after_trade(asset_1, amount_asset_1, 'sell')
                        await self.update_portfolio_after_trade(asset_2, order_size_buy, 'buy')
                elif action == 'buy':
                    # Sell asset_2 for USDT, then buy asset_1 with USDT
                    order_id_sell = await self.place_limit_order(
                        price=self.current_prices[asset_2],
                        order_type='sell',
                        order_size=amount_asset_2,
                        asset=asset_2
                    )
                    usdt_amount = amount_asset_2 * self.current_prices[asset_2]
                    order_size_buy = usdt_amount / self.current_prices[asset_1]
                    order_id_buy = await self.place_limit_order(
                        price=self.current_prices[asset_1],
                        order_type='buy',
                        order_size=order_size_buy,
                        asset=asset_1
                    )
                    if order_id_sell and order_id_buy:
                        # Update portfolio
                        await self.update_portfolio_after_trade(asset_2, amount_asset_2, 'sell')
                        await self.update_portfolio_after_trade(asset_1, order_size_buy, 'buy')
        else:
            logging.info(f"Trade between {asset_1} and {asset_2} not executed as it doesn't improve portfolio balance.")

    def calculate_deviations_for_portfolio(self, portfolio: Dict[str, float], total_value: float) -> Dict[str, float]:
        """Calculate deviations for a given portfolio."""
        deviations = {}
        for asset, target_weight in zip(self.assets, self.target_weights):
            current_value = portfolio[asset] * self.current_prices[asset]
            current_weight = current_value / total_value if total_value > 0 else 0
            deviation = target_weight - current_weight  # Target - Current
            deviations[asset] = deviation
        return deviations

    async def place_limit_order(self, price, order_type, order_size, asset, quote_asset='USDT'):
        """Place a limit order using Binance API."""
        symbol = f"{asset}{quote_asset}"
        side = 'BUY' if order_type == 'buy' else 'SELL'

        try:
            # Fetch symbol info to get the correct precision
            symbol_info = await self.client.get_symbol_info(symbol)
            if symbol_info is None:
                logging.error(f"Symbol info not found for {symbol}.")
                return None

            # Extract filters
            filters = symbol_info['filters']
            step_size = float(next(filter(lambda f: f['filterType'] == 'LOT_SIZE', filters))['stepSize'])
            min_qty = float(next(filter(lambda f: f['filterType'] == 'LOT_SIZE', filters))['minQty'])
            max_qty = float(next(filter(lambda f: f['filterType'] == 'LOT_SIZE', filters))['maxQty'])
            tick_size = float(next(filter(lambda f: f['filterType'] == 'PRICE_FILTER', filters))['tickSize'])
            quantity_precision = int(round(-np.log10(step_size), 0))
            price_precision = int(round(-np.log10(tick_size), 0))
            quantity = round(order_size, quantity_precision)
            price = round(price, price_precision)

            # Ensure quantity and price are within allowed range
            if quantity < min_qty or quantity > max_qty:
                logging.error(f"Order quantity {quantity} out of bounds ({min_qty} - {max_qty}).")
                return None

            # Convert price to string before creating order to avoid encoding error
            price_str = "{:.8f}".format(price).rstrip('0').rstrip('.')
            quantity_str = "{:.8f}".format(quantity).rstrip('0').rstrip('.')

            order = await self.client.create_order(
                symbol=symbol,
                side=side,
                type='LIMIT',
                timeInForce='GTC',
                quantity=quantity_str,
                price=price_str
            )
            order_id = order['orderId']
            logging.info(f"Placed {side} LIMIT order on {symbol} for {quantity} at {price}, Order ID: {order_id}")
            return order_id
        except BinanceAPIException as e:
            logging.error(f"Binance API Exception: {e}")
        except BinanceOrderException as e:
            logging.error(f"Binance Order Exception: {e}")
        except Exception as e:
            logging.error(f"Order placement failed: {e}")
        return None

    async def get_historical_prices(self, asset: str, interval: str = '1m', limit: int = 100):
        """Fetch historical prices for a given asset."""
        try:
            current_time = time.time()
            cache_entry = self.historical_data_cache.get(asset)
            if cache_entry and current_time - cache_entry['timestamp'] < 3600:  # 1 hour cache expiry
                return cache_entry['prices']
            else:
                klines = await self.client.get_klines(symbol=f"{asset}USDT", interval=interval, limit=limit)
                prices = [float(kline[4]) for kline in klines]  # Closing prices
                self.historical_data_cache[asset] = {'prices': prices, 'timestamp': current_time}
                return prices
        except Exception as e:
            logging.error(f"Error fetching historical prices for {asset}: {e}")
            return []

    async def cancel_open_orders(self):
        """Cancel all open orders before rebalancing."""
        try:
            for order_id in list(self.orders.keys()):
                order = self.orders[order_id]
                if order['status'] == 'open':
                    symbol = f"{order['asset']}USDT"
                    await self.client.cancel_order(symbol=symbol, orderId=order_id)
                    logging.info(f"Canceled order {order_id} on {symbol}")
                    order['status'] = 'canceled'
        except Exception as e:
            logging.error(f"Error canceling open orders: {e}")

    async def update_portfolio_after_trade(self, asset: str, amount: float, order_type: str):
        """Update the portfolio after an order is executed."""
        if order_type == 'buy':
            self.portfolio[asset] += amount
            logging.info(f"Bought {amount:.6f} {asset}. New balance: {self.portfolio[asset]:.6f} {asset}.")
        elif order_type == 'sell':
            self.portfolio[asset] -= amount
            logging.info(f"Sold {amount:.6f} {asset}. New balance: {self.portfolio[asset]:.6f} {asset}.")

    async def run(self):
        self.client = await AsyncClient.create(self.api_key, self.api_secret)
        try:
            # Initialize current prices
            for asset in self.assets:
                ticker = await self.client.get_symbol_ticker(symbol=f"{asset}USDT")
                self.current_prices[asset] = float(ticker['price'])
                self.price_history[asset].append(self.current_prices[asset])

                # Fetch historical prices if Bollinger Bands are used
                if self.use_bollinger_bands:
                    historical_prices = await self.get_historical_prices(asset)
                    self.price_history[asset].extend(historical_prices)
                    # Ensure price history length is consistent
                    self.price_history[asset] = self.price_history[asset][-100:]

            await self.initialize_portfolio()
            await self.websocket_price_updates()
        finally:
            await self.client.close_connection()

    async def initialize_portfolio(self):
        """Initialize the portfolio based on total funds or asset funds."""
        if self.asset_funds:
            for asset in self.assets:
                amount = self.asset_funds.get(asset, 0) / self.current_prices[asset]
                self.portfolio[asset] = amount
        elif self.total_funds:
            for asset, weight in zip(self.assets, self.target_weights):
                amount = (self.total_funds * weight) / self.current_prices[asset]
                self.portfolio[asset] = amount
        logging.info(f"Initialized portfolio: {self.portfolio}")

if __name__ == "__main__":
    async def main():
        index_fund = IndexFundCalculator(
            assets=['BTC', 'ETH',],
            target_weights=[0.5, 0.5,],  # Ensure these sum to 1
            total_funds=10000,
            asset_funds=None,
            num_levels=4,
            orders_per_level=3,
            use_bollinger_bands=True,
            use_pairwise_trading=True,  # Pairwise trading is optional and enabled here
            increased_risk=True,
            use_weighted_orders=True,  # Enable weighted orders
            pairwise_trade_fraction=0.005  # Small fraction for incremental adjustments
        )
        await index_fund.run()

    asyncio.run(main())
