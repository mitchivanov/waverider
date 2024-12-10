import time
import math
from binance.client import Client
from binance.enums import SIDE_SELL, ORDER_TYPE_LIMIT, TIME_IN_FORCE_GTC

class SellBot:
    def __init__(self, api_key, api_secret, min_price, max_price, num_levels, reset_threshold_pct, pair, batch_size):
        self.client = Client(api_key, api_secret, testnet=True)
        self.min_price = min_price
        self.max_price = max_price
        self.num_levels = num_levels
        self.reset_threshold_pct = reset_threshold_pct
        self.pair = pair
        self.batch_size = batch_size

        self.sell_levels = self.generate_sell_levels()
        self.open_orders = []
        self.last_filled_price = None

    def generate_sell_levels(self):
        """Generate sell levels based on min, max price, and fixed intervals."""
        interval = (self.max_price - self.min_price) / (self.num_levels - 1)
        return [round(self.min_price + i * interval, 2) for i in range(self.num_levels)]

    def place_batch_orders(self):
        """Place sell orders in batches."""
        for level in self.sell_levels:
            if not self.is_order_already_placed(level):
                try:
                    order = self.client.create_order(
                        symbol=self.pair,
                        side=SIDE_SELL,
                        type=ORDER_TYPE_LIMIT,
                        timeInForce=TIME_IN_FORCE_GTC,
                        quantity=self.batch_size,
                        price=f"{level:.2f}"
                    )
                    self.open_orders.append({'price': level, 'orderId': order['orderId']})
                    print(f"Order placed at level: {level}")
                except Exception as e:
                    print(f"Error placing order at level {level}: {e}")

    def is_order_already_placed(self, level):
        """Check if an order is already placed at a specific level."""
        tolerance = 0.01  # Allow for slight rounding discrepancies
        return any(math.isclose(order['price'], level, abs_tol=tolerance) for order in self.open_orders)

    def monitor_orders(self):
        """Monitor and update order statuses."""
        for order in list(self.open_orders):
            try:
                status = self.client.get_order(
                    symbol=self.pair,
                    orderId=order['orderId']
                )
                if status['status'] == 'FILLED':
                    self.last_filled_price = float(status['price'])
                    print(f"Order filled at price: {self.last_filled_price}")
                    self.open_orders.remove(order)
            except Exception as e:
                print(f"Error checking order {order['orderId']}: {e}")

    def reset_missing_orders(self, current_price):
        """Reset missing sell orders if the price drops below the reset threshold."""
        if self.last_filled_price and current_price < self.last_filled_price * (1 - self.reset_threshold_pct / 100):
            for level in self.sell_levels:
                if level not in [order['price'] for order in self.open_orders] and level <= current_price:
                    try:
                        order = self.client.create_order(
                            symbol=self.pair,
                            side=SIDE_SELL,
                            type=ORDER_TYPE_LIMIT,
                            timeInForce=TIME_IN_FORCE_GTC,
                            quantity=self.batch_size,
                            price=f"{level:.2f}"
                        )
                        self.open_orders.append({'price': level, 'orderId': order['orderId']})
                        print(f"Replaced missing order at level: {level}")
                    except Exception as e:
                        print(f"Error placing missing order at level {level}: {e}")
    def fetch_market_price(self):
        """Fetch the current market price."""
        try:
            ticker = self.client.get_symbol_ticker(symbol=self.pair)
            return float(ticker['price'])
        except Exception as e:
            print(f"Error fetching market price: {e}")
            return None

    def run(self):
        """Main loop to manage orders."""
        self.place_batch_orders()
        while True:
            current_price = self.fetch_market_price()
            if current_price:
                self.monitor_orders()
                self.reset_missing_orders(current_price)
            time.sleep(5)  # Adjust frequency as needed
            
            
            
    #TODO Выводить, сколько заработано и сколько сделано ордеров