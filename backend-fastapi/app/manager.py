import asyncio
import logging
from gridstrat import start_grid_strategy, stop_grid_strategy, GridStrategy
from models.models import TradingParameters, ActiveOrder, TradeHistory, OrderHistory
from sqlalchemy import delete
from sqlalchemy.future import select
from database import async_session
from typing import Optional, Dict, List
import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='grid_trading.log'
)

class TradingBotManager:
    _bots: Dict[int, GridStrategy] = {}
    _tasks: Dict[int, asyncio.Task] = {}
    _start_times: Dict[int, datetime.datetime] = {}

    @classmethod
    async def is_running(cls, bot_id: int) -> bool:
        return bot_id in cls._bots

    @classmethod
    async def start_bot(cls, bot_id: int, parameters: dict):
        try:
            if await cls.is_running(bot_id):
                await cls.stop_bot(bot_id)
            
            strategy = await start_grid_strategy(parameters)
            cls._bots[bot_id] = strategy
            cls._start_times[bot_id] = datetime.datetime.now()
            
            logging.info(f"Бот {bot_id} успешно запущен")
            return True
        except Exception as e:
            logging.error(f"Ошибка при запуске бота {bot_id}: {e}")
            raise e

    @classmethod
    async def stop_bot(cls, bot_id: int):
        if bot_id in cls._bots:
            try:
                logging.info(f"Останавливаем бот {bot_id}")
                await stop_grid_strategy(cls._bots[bot_id])
                del cls._bots[bot_id]
                if bot_id in cls._start_times:
                    del cls._start_times[bot_id]
                if bot_id in cls._tasks:
                    cls._tasks[bot_id].cancel()
                    del cls._tasks[bot_id]
                
                logging.info(f"Бот {bot_id} успешно остановлен")
                return True
            except Exception as e:
                logging.error(f"Ошибка при остановке бота {bot_id}: {e}")
                raise

    @classmethod
    async def get_current_parameters(cls, bot_id: int) -> Optional[dict]:
        if bot_id in cls._bots:
            parameters = await cls._bots[bot_id].get_strategy_status()
            return {
                "bot_id": bot_id,
                "status": parameters["status"],
                "current_price": parameters["current_price"],
                "initial_price": parameters["initial_price"],
                "deviation": parameters["deviation"],
                "realized_profit_a": parameters["realized_profit_a"],
                "realized_profit_b": parameters["realized_profit_b"],
                "total_profit_usdt": parameters["total_profit_usdt"],
                
                "running_time": parameters["running_time"],
                
                "active_orders_count": parameters["active_orders_count"],
                "completed_trades_count": parameters["completed_trades_count"],
                
                "unrealized_profit_a": parameters["unrealized_profit"]["unrealized_profit_a"],
                "unrealized_profit_b": parameters["unrealized_profit"]["unrealized_profit_b"],
                "unrealized_profit_usdt": parameters["unrealized_profit"]["total_unrealized_profit_usdt"],
                
                "active_orders": parameters["active_orders"],
                
                "initial_parameters": parameters["initial_parameters"]
            }
        return None

    @classmethod
    async def get_active_orders_list(cls, bot_id: int) -> List[ActiveOrder]:
        async with async_session() as session:
            result_orders = await session.execute(
                select(ActiveOrder).where(ActiveOrder.bot_id == bot_id)
            )
            return list(result_orders.scalars().all())
    
    @classmethod
    async def get_all_trades_list(cls) -> List[TradeHistory]:
        async with async_session() as session:
            result_trades = await session.execute(select(TradeHistory))
            trade_history = result_trades.scalars().all()
            return list(trade_history)

    @classmethod
    async def get_order_history_list(cls) -> List[OrderHistory]:
        async with async_session() as session:
            result = await session.execute(select(OrderHistory))
            order_history = result.scalars().all()
            return list(order_history)

    @classmethod
    async def get_all_bots(cls) -> List[int]:
        """Возвращает список ID всех активных ботов"""
        return list(cls._bots.keys())

    @classmethod
    async def get_bot_status(cls, bot_id: int) -> Optional[str]:
        """Возвращает статус конкретного бота"""
        if bot_id in cls._bots:
            return "active"
        return None

    @classmethod
    async def get_bot_uptime(cls, bot_id: int) -> Optional[float]:
        """Возвращает время работы бота в секундах"""
        if bot_id in cls._start_times:
            return (datetime.datetime.now() - cls._start_times[bot_id]).total_seconds()
        return None
