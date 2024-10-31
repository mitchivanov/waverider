import asyncio
import logging
from gridstrat import start_grid_strategy, stop_grid_strategy, GridStrategy
from models.models import TradingParameters, ActiveOrder, TradeHistory
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
    _instance: Optional[GridStrategy] = None
    _bot_task: Optional[asyncio.Task] = None
    _start_time: Optional[datetime.datetime] = None

    @classmethod
    async def is_running(cls) -> bool:
        return cls._instance is not None

    @classmethod
    async def start_bot(cls, parameters: dict):
        try:
            if await cls.is_running():
                await cls.stop_bot()
            
            cls._instance = await start_grid_strategy(parameters)
            cls._start_time = datetime.datetime.now()
            
            logging.info("Бот успешно запущен")
            return True
        except Exception as e:
            logging.error(f"Ошибка при запуске бота: {e}")
            raise e

    @classmethod
    async def stop_bot(cls):
        if cls._instance:
            try:
                await stop_grid_strategy(cls._instance)
                cls._instance = None
                cls._start_time = None
                cls._bot_task = None
                
                logging.info("Бот успешно остановлен")
                return True
            except Exception as e:
                logging.error(f"Ошибка при остановке бота: {e}")
                raise

    @classmethod
    async def get_current_parameters(cls) -> Optional[dict]:
        if cls._instance:
            # Получаем статус стратегии и ожидаем результат
            parameters = await cls._instance.get_strategy_status()
            
            return {
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
    async def get_active_orders_list(cls) -> List[ActiveOrder]:
        async with async_session() as session:
            result_orders = await session.execute(select(ActiveOrder))
            active_orders = result_orders.scalars().all()
            return list(active_orders)
    
    @classmethod
    async def get_all_trades_list(cls) -> List[TradeHistory]:
        async with async_session() as session:
            result_trades = await session.execute(select(TradeHistory))
            trade_history = result_trades.scalars().all()
            return list(trade_history)
