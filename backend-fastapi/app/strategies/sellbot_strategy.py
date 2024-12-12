import time
import math
from binance.client import Client
from binance.enums import SIDE_SELL, ORDER_TYPE_LIMIT, TIME_IN_FORCE_GTC
from strategies.base_strategy import BaseStrategy
from database import async_session
from models.models import TradeHistory, ActiveOrder, OrderHistory
import datetime
import logging
from sqlalchemy.future import select
from sqlalchemy import delete, update
from strategies.logger import AsyncLogger
import asyncio

class SellBot(BaseStrategy):
    def __init__(self, bot_id, api_key, api_secret, min_price, max_price, num_levels, reset_threshold_pct, pair, batch_size, testnet=True):
        logging.info(f"Инициализация SellBot для пары {pair}")
        logging.info(f"Параметры: min_price={min_price}, max_price={max_price}, "
                    f"num_levels={num_levels}, reset_threshold_pct={reset_threshold_pct}, "
                    f"batch_size={batch_size}")
        
        self.bot_id = bot_id
        self.client = Client(api_key, api_secret, testnet=testnet)
        self.min_price = float(min_price)
        self.max_price = float(max_price)
        self.num_levels = int(num_levels)
        self.reset_threshold_pct = float(reset_threshold_pct)
        self.pair = str(pair)
        self.batch_size = float(batch_size)
        
        self.sell_levels = self.generate_sell_levels()
        self.active_orders = []
        self.last_filled_price = None
        self.trades_logger = AsyncLogger(bot_id)
        self.realized_profit = 0
        self.total_orders = 0

    def generate_sell_levels(self):
        """Generate sell levels based on min, max price, and fixed intervals."""
        logging.info(f"Генерация уровней для пары {self.pair}")
        interval = (self.max_price - self.min_price) / (self.num_levels - 1)
        return [round(self.min_price + i * interval, 2) for i in range(self.num_levels)]

    async def place_batch_orders(self):
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
                    
                    # Сохраняем ордер в базу данных
                    order_data = {
                        'order_id': str(order['orderId']),
                        'order_type': 'sell',
                        'isInitial': True,
                        'price': float(level),
                        'quantity': float(self.batch_size)
                    }
                    
                    await self.add_active_order(self.bot_id, order_data)
                    await self.add_order_to_history(
                        bot_id=self.bot_id,
                        order_id=str(order['orderId']),
                        order_type='sell',
                        isInitial=True,
                        status='OPEN',
                        price=float(level),
                        quantity=float(self.batch_size)
                    )
                    
                    self.total_orders += 1
                    await self.trades_logger.log(f"Order placed at level: {level}")
                    
                except Exception as e:
                    await self.trades_logger.error(f"Error placing order at level {level}: {e}")

    def is_order_already_placed(self, level):
        """Check if an order is already placed at a specific level."""
        tolerance = 0.01  # Allow for slight rounding discrepancies
        return any(math.isclose(order['price'], level, abs_tol=tolerance) for order in self.active_orders)

    async def monitor_orders(self):
        """Monitor and update order statuses."""
        for order in list(self.active_orders):
            try:
                status = self.client.get_order(
                    symbol=self.pair,
                    orderId=order['order_id']
                )
                if status['status'] == 'FILLED':
                    self.last_filled_price = float(status['price'])
                    await self.trades_logger.log(f"Order filled at price: {self.last_filled_price}")
                    await self.update_trade_history(status)
                    await self.remove_active_order(self.bot_id, str(order['order_id']))
                    
            except Exception as e:
                await self.trades_logger.error(f"Error checking order {order['order_id']}: {e}")

    async def reset_missing_orders(self, current_price):
        """Reset missing sell orders if the price drops below the reset threshold."""
        if self.last_filled_price and current_price < self.last_filled_price * (1 - self.reset_threshold_pct / 100):
            for level in self.sell_levels:
                if level not in [order['price'] for order in self.active_orders] and level <= current_price:
                    try:
                        order = self.client.create_order(
                            symbol=self.pair,
                            side=SIDE_SELL,
                            type=ORDER_TYPE_LIMIT,
                            timeInForce=TIME_IN_FORCE_GTC,
                            quantity=self.batch_size,
                            price=f"{level:.2f}"
                        )
                        self.active_orders.append({'price': level, 'orderId': order['orderId']})
                        await self.trades_logger.log(f"Replaced missing order at level: {level}")
                    except Exception as e:
                        await self.trades_logger.error(f"Error placing missing order at level {level}: {e}")
                        
    async def fetch_market_price(self):
        """Fetch the current market price."""
        try:
            ticker = self.client.get_symbol_ticker(symbol=self.pair)
            return float(ticker['price'])
        except Exception as e:
            logging.error(f"Error fetching market price: {e}")
            return None

    async def execute_strategy(self):
        """Основной метод исполнения стратегии"""
        
        logging.info(f"Инициация стратегии sellbot для пары {self.pair}")
        try:
            self.stop_flag = False
            await self.place_batch_orders()
            while not self.stop_flag:
                current_price = await self.fetch_market_price()
                if current_price:
                    await self.monitor_orders()
                    await self.reset_missing_orders(current_price)
                await asyncio.sleep(5)
        except Exception as e:
            await self.trades_logger.error(f"Error in execute_strategy: {e}")
            
    async def stop_strategy(self):
        """Метод остановки стратегии"""
        try:
            self.stop_flag = True
            # Отменяем все активные ордера
            for order in self.active_orders:
                try:
                    self.client.cancel_order(
                        symbol=self.pair,
                        order_id=order['orderId']
                    )
                except Exception as e:
                    await self.trades_logger.error(f"Error canceling order {order['orderId']}: {e}")
            
            # Очищаем состояние
            self.active_orders = []
            await self.trades_logger.log("Strategy stopped")
            return True
        except Exception as e:
            await self.trades_logger.error(f"Error stopping strategy: {e}")
            raise

    async def update_trade_history(self, order):
        """Update trade history when order is filled"""
        try:
            # Обновляем статус ордера в истории
            async with async_session() as session:
                await session.execute(
                    update(OrderHistory)
                    .where(OrderHistory.order_id == str(order['orderId']))
                    .values(status='FILLED')
                )
                await session.commit()

            trade_data = {
                'bot_id': self.bot_id,
                'sell_price': float(order['price']),
                'quantity': float(order['executedQty']),
                'profit': float(order['price']) * float(order['executedQty']),
                'profit_asset': self.pair[-4:],
                'status': 'CLOSED',
                'trade_type': 'SELL',
                'sell_order_id': str(order['orderId'])
            }
            
            self.realized_profit += trade_data['profit']
            
        except Exception as e:
            await self.trades_logger.error(f"Error updating trade history: {e}")

    async def get_strategy_status(self, bot_id: int):
        """Get current strategy status"""
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(ActiveOrder).where(ActiveOrder.bot_id == bot_id)
                )
                active_orders = result.scalars().all()
                
                return {
                    "bot_id": bot_id,
                    "status": "active",
                    "current_price": await self.fetch_market_price(),
                    "realized_profit": self.realized_profit,
                    "total_orders": self.total_orders,
                    "active_orders_count": len(active_orders),
                    "initial_parameters": {
                        "pair": self.pair,
                        "min_price": self.min_price,
                        "max_price": self.max_price,
                        "num_levels": self.num_levels,
                        "reset_threshold_pct": self.reset_threshold_pct,
                        "batch_size": self.batch_size
                    }
                }
        except Exception as e:
            await self.trades_logger.error(f"Error getting strategy status: {e}")
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
            
        except Exception as e:
            await self.trades_logger.panic(f"Error removing active order {order_id}: {e}")
        
        
    #TODO Выводить, сколько заработано и сколько сделано ордеров