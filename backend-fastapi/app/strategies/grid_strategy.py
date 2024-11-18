from typing import Dict, List
import logging
import asyncio
import datetime
from abc import ABC, abstractmethod
from binance.client import Client

from components.order_manager import OrderManager
from components.price_manager import PriceManager
from components.database_manager import DatabaseManager
from components.profit_calculator import ProfitCalculator
    
class GridStrategyBase(ABC):
    """Базовый абстрактный класс для грид-стратегий"""

    @abstractmethod
    async def execute_strategy(self):
        pass

    @abstractmethod
    async def calculate_grid_levels(self, current_price: float):
        pass

class StandardGridStrategy(GridStrategyBase):
    """Стандартная реализация грид-стратегии"""

    def __init__(self, config: Dict, binance_client: Client):
        self.symbol = config['symbol']
        self.grids = config['grids']
        self.deviation_threshold = config['deviation_threshold']
        self.growth_factor = config.get('growth_factor', 1.0)
        self.use_granular_distribution = config.get('use_granular_distribution', False)
        self.trail_price = config.get('trail_price', True)
        self.only_profitable_trades = config.get('only_profitable_trades', False)
        self.stop_flag = False

        # Инициализация компонентов
        self.db_manager = DatabaseManager()
        self.order_manager = OrderManager(binance_client, self.db_manager, self.symbol)
        self.price_manager = PriceManager(self.symbol, self.on_price_update)
        self.profit_calculator = ProfitCalculator()

        # Состояние стратегии
        self.grid_levels = {'buy': [], 'sell': []}
        self.current_price = None
        self.initial_price = None
        self.deviation = None
        self.realized_profit_a = 0.0
        self.realized_profit_b = 0.0
        self.unrealized_profit_a = 0.0
        self.unrealized_profit_b = 0.0
        self.open_trades = []
        self.active_orders = []
        self.trade_history = []
        self.start_time = datetime.datetime.now()

    async def execute_strategy(self):
        """Основной метод исполнения стратегии"""
        try:
            await self.price_manager.start_price_updates()

            while not self.stop_flag:
                if self.current_price is None:
                    await asyncio.sleep(1)
                    continue

                if self.initial_price is None:
                    self.initial_price = self.current_price
                    await self.initialize_grid()

                # Проверка отклонения от начальной цены
                self.deviation = (self.current_price - self.initial_price) / self.initial_price
                if abs(self.deviation) >= self.deviation_threshold:
                    await self.reset_grid()
                    continue

                # Проверка и исполнение ордеров
                await self.check_and_execute_orders()

                # Проверка открытых позиций
                await self.check_open_trades()

                await asyncio.sleep(1)  # Пауза между итерациями

        except asyncio.CancelledError:
            logging.info("Стратегия прервана задачей.")
        except Exception as e:
            logging.error(f"Ошибка в исполнении стратегии: {str(e)}")
        finally:
            await self.cleanup()

    async def initialize_grid(self):
        """Инициализация сетки"""
        await self.calculate_grid_levels(self.initial_price)
        await self.place_initial_orders()

    async def calculate_grid_levels(self, current_price: float):
        """Расчет уровней сетки"""
        step_distance = (self.deviation_threshold / self.grids) * current_price

        self.grid_levels['buy'] = [
            current_price - (i * step_distance) 
            for i in range(1, self.grids + 1)
        ]
        self.grid_levels['sell'] = [
            current_price + (i * step_distance) 
            for i in range(1, self.grids + 1)
        ]

        logging.info(f"Расчет уровней сетки завершен. Buy: {self.grid_levels['buy']}, Sell: {self.grid_levels['sell']}")

    async def check_and_execute_orders(self):
        """Проверка и исполнение ордеров"""
        tasks = []
        for idx, price_level in enumerate(self.grid_levels['buy']):
            if self.current_price <= price_level:
                quantity = self.buy_order_sizes[idx]
                tasks.append(self.order_manager.place_buy_order(price_level, quantity))

        for idx, price_level in enumerate(self.grid_levels['sell']):
            if self.current_price >= price_level:
                quantity = self.sell_order_sizes[idx]
                tasks.append(self.order_manager.place_sell_order(price_level, quantity))

        if tasks:
            await asyncio.gather(*tasks)

    async def reset_grid(self):
        """Сброс сетки при достижении отклонения"""
        await self.order_manager.cancel_all_orders()
        self.initial_price = self.current_price
        await self.initialize_grid()

    async def cleanup(self):
        """Очистка ресурсов при остановке"""
        await self.order_manager.cancel_all_orders()
        await self.price_manager.stop_price_updates()
        logging.info("Ресурсы стратегии очищены.")

    def on_price_update(self, new_price: float):
        """Callback для обновления текущей цены"""
        self.current_price = new_price
        logging.debug(f"Текущая цена обновлена: {self.current_price}")

    async def place_initial_orders(self):
        """Размещает начальные ордера"""
        if self.use_granular_distribution:
            await self.calculate_order_sizes()
        else:
            await self.calculate_order_sizes_equal()

        for price_level, qty in zip(self.grid_levels['buy'], self.buy_order_sizes):
            await self.order_manager.place_buy_order(price_level, qty)

        for price_level, qty in zip(self.grid_levels['sell'], self.sell_order_sizes):
            await self.order_manager.place_sell_order(price_level, qty)

        logging.info("Начальные ордера размещены.")

    async def calculate_order_sizes(self):
        """Вычисляет размеры ордеров при использовании гранулярного распределения"""
        total_buy_funds = self.asset_a_funds
        x1 = total_buy_funds / (self.grids + (self.growth_factor * (self.grids * (self.grids - 1)) / 2))
        self.buy_order_sizes = [
            (x1 + self.growth_factor * i * x1) / self.current_price  # Перевод в количество базового актива
            for i in range(self.grids)
        ]

        logging.debug(f"Total buy funds: {total_buy_funds} USDT")
        logging.debug(f"Growth factor: {self.growth_factor}")
        logging.debug(f"Initial buy order size (x1): {x1}")

        total_sell_quantity = self.asset_b_funds
        x1_sell = total_sell_quantity / (self.grids + (self.growth_factor * (self.grids * (self.grids - 1)) / 2))
        self.sell_order_sizes = [x1_sell + self.growth_factor * i * x1_sell for i in range(self.grids)]

        logging.debug(f"Total sell quantity: {total_sell_quantity} BTC")
        logging.debug(f"Initial sell order size (x1_sell): {x1_sell}")

    async def calculate_order_sizes_equal(self):
        """Вычисляет размеры ордеров при равномерном распределении"""
        total_buy_funds = self.asset_a_funds
        buy_funds_per_grid = total_buy_funds / self.grids
        self.buy_order_sizes = [buy_funds_per_grid / self.current_price for _ in range(self.grids)]

        logging.debug(f"Buy funds per grid: {buy_funds_per_grid} USDT")

        total_sell_quantity = self.asset_b_funds
        sell_quantity_per_grid = total_sell_quantity / self.grids
        self.sell_order_sizes = [sell_quantity_per_grid for _ in range(self.grids)]

        logging.debug(f"Sell quantity per grid: {sell_quantity_per_grid} BTC")

    async def check_open_trades(self):
        """Проверяет открытые позиции и рассчитывает прибыль"""
        unrealized = self.profit_calculator.calculate_unrealized_profit_loss(self.open_trades, self.current_price)
        total_profit = self.profit_calculator.get_total_profit_usdt(
            self.realized_profit_a, 
            self.realized_profit_b, 
            self.current_price
        )
        self.unrealized_profit_a = unrealized["unrealized_profit_a"]
        self.unrealized_profit_b = unrealized["unrealized_profit_b"]

        logging.info(f"Нереализованная прибыль: {unrealized}, Общая прибыль: {total_profit}")