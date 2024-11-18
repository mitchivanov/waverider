import asyncio
import logging
from typing import Optional, Dict
from datetime import datetime

from .grid_strategy import StandardGridStrategy
from binance.client import Client
from sqlalchemy.future import select
from database import async_session
from models.models import ActiveOrder, TradeHistory

class StrategyManager:
    """Модуль для управления состоянием стратегии"""

    def __init__(self):
        self.strategy_instance: Optional[StandardGridStrategy] = None
        self.strategy_task: Optional[asyncio.Task] = None

    async def start_strategy(self, config: Dict, binance_client: Client):
        """Запускает стратегию"""
        if self.strategy_instance and self.strategy_task and not self.strategy_task.done():
            logging.warning("Стратегия уже запущена.")
            return

        self.strategy_instance = StandardGridStrategy(config, binance_client)
        self.strategy_task = asyncio.create_task(self.strategy_instance.execute_strategy())
        logging.info("Стратегия успешно запущена.")

    async def stop_strategy(self):
        """Останавливает стратегию"""
        if self.strategy_instance:
            self.strategy_instance.stop_flag = True
            await self.strategy_instance.cleanup()
            if self.strategy_task:
                self.strategy_task.cancel()
                try:
                    await self.strategy_task
                except asyncio.CancelledError:
                    logging.info("Таск стратегии успешно отменен.")
            self.strategy_instance = None
            logging.info("Стратегия успешно остановлена.")
        else:
            logging.warning("Стратегия не запущена.")

    async def get_strategy_status(self) -> Dict:
        """Возвращает текущий статус стратегии."""
        if self.strategy_instance and self.strategy_task:
            current_time = datetime.now()
            running_time = current_time - self.strategy_instance.start_time if hasattr(self.strategy_instance, 'start_time') else None

            # Получение общей прибыли в USDT
            total_profit_usdt = self.strategy_instance.profit_calculator.get_total_profit_usdt(
                self.strategy_instance.realized_profit_a, 
                self.strategy_instance.realized_profit_b, 
                self.strategy_instance.current_price
            )

            # Расчет нереализованной прибыли
            unrealized_profit = self.strategy_instance.profit_calculator.calculate_unrealized_profit_loss(
                self.strategy_instance.open_trades,
                self.strategy_instance.current_price
            )

            # Получение количества активных ордеров из базы данных
            async with async_session() as session:
                result = await session.execute(select(ActiveOrder))
                active_orders = result.scalars().all()
                active_orders_count = len(active_orders)

            # Получение количества завершенных сделок
            completed_trades_count = len([t for t in self.strategy_instance.trade_history if t['status'] == 'CLOSED'])

            return {
                "status": "active" if not self.strategy_instance.stop_flag else "inactive",
                "current_price": self.strategy_instance.current_price,
                "initial_price": self.strategy_instance.initial_price,
                "deviation": self.strategy_instance.deviation,
                "realized_profit_a": self.strategy_instance.realized_profit_a,
                "realized_profit_b": self.strategy_instance.realized_profit_b,
                "total_profit_usdt": total_profit_usdt,
                "running_time": str(running_time) if running_time else None,
                "active_orders_count": active_orders_count,
                "completed_trades_count": completed_trades_count,
                "unrealized_profit": unrealized_profit,
                "active_orders": [
                    {
                        "order_id": order.order_id,
                        "order_type": order.order_type,
                        "price": order.price,
                        "quantity": order.quantity,
                        "created_at": order.created_at
                    } for order in self.strategy_instance.active_orders
                ],
                "initial_parameters": {
                    "symbol": self.strategy_instance.symbol,
                    "asset_a_funds": self.strategy_instance.asset_a_funds,
                    "asset_b_funds": self.strategy_instance.asset_b_funds,
                    "grids": self.strategy_instance.grids,
                    "deviation_threshold": self.strategy_instance.deviation_threshold,
                    "growth_factor": self.strategy_instance.growth_factor,
                    "use_granular_distribution": self.strategy_instance.use_granular_distribution,
                    "trail_price": self.strategy_instance.trail_price,
                    "only_profitable_trades": self.strategy_instance.only_profitable_trades
                }
            }
        else:
            return {"running": False}