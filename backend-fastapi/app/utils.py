import logging
import decimal
import datetime
import asyncio
from binance_client import BinanceClient
from asyncio_throttle import Throttler
from sqlalchemy.ext.asyncio import async_session
from sqlalchemy import delete, update, select
from models.models import ActiveOrder, TradeHistory
from binance_websocket import BinanceWebSocket
from abc import ABC, abstractmethod
 
class BinanceService:
    
    def __init__(self, api_key, api_secret, symbol):
        super().__init__(api_key, api_secret)
        self.symbol = symbol.upper()
        self.websocket = BinanceWebSocket(self.symbol)
    
    async def get_account_balance(self, asset):
        """Get balance for specific asset."""
        account_info = self.binance_client.client.get_account()
        balances = {
            balance['asset']: float(balance['free']) 
            for balance in account_info['balances']
        }
        return balances.get(asset, 0)


    async def close_all_sessions(self):
        """Close all active sessions."""
        if self.websocket:
            await self.websocket.stop()

    async def handle_error(self, error: Exception, context: str):
        """Handle errors in a standardized way."""
        logging.error(f"Error in {context}: {str(error)}")

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

class OrderService:
    def __init__(self, binance_client, symbol, asset_a_funds, asset_b_funds):
        self.binance_client = binance_client
        self.symbol = symbol.upper()
        self.asset_a_funds = asset_a_funds
        self.asset_b_funds = asset_b_funds
        self.throttler = Throttler(rate_limit=5, period=1)
        self.websocket = BinanceWebSocket(self.symbol)
        self.active_orders = []  # Перемещено из GridStrategy
        self.buy_positions = []   # Добавлено
        self.sell_positions = []  # Добавлено

    def is_balance_sufficient(self, order_type, price, quantity):
        """Проверяет, достаточно ли баланса для размещения ордера."""
        try:
            account_info = self.binance_client.client.get_account()
            balances = {
                balance['asset']: float(balance['free']) 
                for balance in account_info['balances']
            }

            quote_asset = self.symbol[-4:]  # Например, 'USDT'
            base_asset = self.symbol[:-4]   # Например, 'BTC'

            if order_type.lower() == 'buy':
                required_quote = price * quantity
                available_quote = balances.get(quote_asset, 0)
                
                if available_quote < required_quote:
                    logging.warning(
                        f"Недостаточно {quote_asset} на балансе. "
                        f"Требуется: {required_quote:.8f}, Доступно: {available_quote:.8f}"
                    )
                    return False
                    
            elif order_type.lower() == 'sell':
                required_base = quantity
                available_base = balances.get(base_asset, 0)
                
                if available_base < required_base:
                    logging.warning(
                        f"Недостаточно {base_asset} на балансе. "
                        f"Требуется: {required_base:.8f}, Доступно: {available_base:.8f}"
                    )
                    return False

            return True

        except Exception as e:
            logging.error(f"Ошибка при проверке баланса: {e}")
            return False  # Лучше возвращать False в случае ошибки

    async def place_limit_order(self, price, order_type, order_size, recvWindow):
        """Place a limit order with proper error handling and validation."""
        logging.info(f"Placing {order_type.upper()} order at ${price} for {order_size} units.")
        async with self.throttler:
            try:
                # Perform a balance check before placing the order
                if not self.is_balance_sufficient(order_type, price, order_size):
                    return

                # Retrieve exchange info
                exchange_info = self.binance_client.client.get_symbol_info(self.symbol)
                if exchange_info is None:
                    logging.error(f"Не удалось получить информацию о символе {self.symbol}.")
                    return None

                # Extract filters
                filters = self.extract_filters(exchange_info)
                if filters is None:
                    logging.error(f"Не удалось извлечь фильтры для символа {self.symbol}.")
                    return None

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
                    logging.error(f"Цена {price} выходит за допустимый диапазон ({min_price} - {max_price}).")
                    return None

                # Ensure quantity is within min and max quantity
                if order_size < min_qty or order_size > max_qty:
                    logging.error(f"Количество {order_size} выходит за допустимый диапазон ({min_qty} - {max_qty}).")
                    return None

                # Ensure order notional is within min and max notional
                notional = price * order_size
                if notional < min_notional or notional > max_notional:
                    logging.error(f"Номинал ордера {notional} выходит за допустимый диапазон ({min_notional} - {max_notional}).")
                    return None

                # Log and place the order
                order = await self.binance_client.place_order_async(
                    self.symbol, order_type.upper(), order_size, price, recvWindow=recvWindow
                )

                if order and 'orderId' in order:

                    # Update positions and active orders

                    order_id = order['orderId']
                    
                    if order_type.lower() == 'buy':
                        self.buy_positions.append({'price': price, 'quantity': order_size, 'order_id': order_id})
                    elif order_type.lower() == 'sell':
                        self.sell_positions.append({'price': price, 'quantity': order_size, 'order_id': order_id})
                    
                    order_data = {
                        'order_id': order_id,
                        'order_type': order_type,
                        'price': price,
                        'quantity': order_size
                    }

                    # Add to database
                    await self.add_active_order(order_data)
                    
                    # Add to memory list
                    self.active_orders.append({
                        'order_id': order_id,
                        'order_type': order_type,
                        'price': price,
                        'quantity': order_size,
                        'created_at': datetime.datetime.now()
                    })
                    
                    # Return the order object
                    return order
                elif order and order.get('code') == -1021:  # Timestamp for this request is outside of the recvWindow
                    # Retry with increased recvWindow
                    return await self.place_limit_order(price, order_type, order_size, recvWindow=5000)
                else:
                    # Handle other API errors
                    error_code = order.get('code')
                    error_msg = order.get('msg')
                    logging.error(f"Failed to place order: {error_code} - {error_msg}")
                    # Return None to indicate failure
                    return None
            except Exception as e:
                logging.error(f"Error placing {order_type.upper()} order at ${price}: {str(e)}")
                logging.exception("Full traceback for order placement error:")
                # Return None to indicate exception occurred
                return None

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
            return None  # Можно выбросить исключение, если предпочтительно

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