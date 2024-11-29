import asyncio
import logging
from strategies.gridstrat import start_grid_strategy, stop_grid_strategy, GridStrategy
#from strategies.otherstrat import start_other_strategy, stop_other_strategy, OtherStrategy
from strategies.strategy_factory import get_strategy_class
from models.models import ActiveOrder, TradeHistory, OrderHistory, BaseBot
from sqlalchemy import delete
from sqlalchemy.future import select
from database import async_session
from typing import Optional, Dict, List, Any
import datetime
from fastapi import HTTPException

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='grid_trading.log'
)

class TradingBotManager:
    _bots: Dict[int, Any] = {}
    _start_times: Dict[int, datetime.datetime] = {}
    
    @classmethod
    async def is_running(cls, bot_id: int) -> bool:
        return bot_id in cls._bots

    @classmethod
    async def start_bot(cls, bot_id: int, bot_type: str, parameters: dict):
        try:
            if await cls.is_running(bot_id):
                await cls.stop_bot(bot_id)
            
            
            parameters['bot_id'] = bot_id
            
            strategy_class = get_strategy_class(bot_type)
            strategy = strategy_class(
                bot_id=bot_id,
                symbol=parameters['symbol'],
                api_key=parameters['api_key'],
                api_secret=parameters['api_secret'],
                testnet=parameters.get('testnet', True),
                asset_a_funds=parameters['asset_a_funds'],
                asset_b_funds=parameters['asset_b_funds'],
                grids=parameters['grids'],
                deviation_threshold=parameters['deviation_threshold'],
                growth_factor=parameters['growth_factor'],
                use_granular_distribution=parameters['use_granular_distribution']
            )
            
            asyncio.create_task(strategy.execute_strategy())
            
            cls._bots[bot_id] = strategy
            cls._start_times[bot_id] = datetime.datetime.now()
            
            logging.info(f"Бот {bot_id} успешно запущен с типом {bot_type}")
            return True
        except Exception as e:
            logging.error(f"Ошибка при запуске бота {bot_id}: {e}")
            raise e

    @classmethod
    async def stop_bot(cls, bot_id: int):
        logging.info(f"Остановка бота {bot_id}")
        if await cls.is_running(bot_id):
            try:
                strategy = cls._bots[bot_id]
                await strategy.stop_strategy()
                
                del cls._bots[bot_id]
                del cls._start_times[bot_id]
                
                logging.info(f"Бот {bot_id} успешно остановлен")
                return True
            except Exception as e:
                logging.error(f"Ошибка при остановке бота {bot_id}: {e}")
                raise e
        else:
            logging.warning(f"Бот {bot_id} не запущен")
            return False

    @classmethod
    async def get_current_parameters(cls, bot_id: int) -> Optional[dict]:
        if await cls.is_running(bot_id):
            strategy = cls._bots[bot_id]
            parameters = await strategy.get_strategy_status()
            
            return {
                "status": parameters["status"],
                "current_price": parameters["current_price"],
                "initial_price": parameters["initial_price"],
                "deviation": parameters["deviation"],
                "realized_profit_a": parameters["realized_profit_a"],
                "realized_profit_b": parameters["realized_profit_b"],
                "total_profit_usdt": parameters["total_profit_usdt"],
                
                "running_time": (datetime.datetime.now() - cls._start_times[bot_id]).total_seconds(),
                
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
            result_orders = await session.execute(select(ActiveOrder).where(ActiveOrder.bot_id == bot_id))
            active_orders = result_orders.scalars().all()
            return list(active_orders)
    
    @classmethod
    async def get_all_trades_list(cls, bot_id: int) -> List[TradeHistory]:
        async with async_session() as session:
            result_trades = await session.execute(select(TradeHistory).where(TradeHistory.bot_id == bot_id))
            trade_history = result_trades.scalars().all()
            return list(trade_history)

    @classmethod
    async def get_order_history_list(cls, bot_id: int) -> List[OrderHistory]:
        async with async_session() as session:
            result = await session.execute(select(OrderHistory).where(OrderHistory.bot_id == bot_id))
            order_history = result.scalars().all()
            return list(order_history)

    @classmethod
    async def get_bot_by_id(cls, bot_id: int) -> BaseBot:
        async with async_session() as session:
            result = await session.execute(select(BaseBot).where(BaseBot.id == bot_id))
            bot = result.scalars().first()
            if not bot:
                logging.error(f"Бот с id {bot_id} не найден.")
                raise HTTPException(status_code=404, detail=f"Бот с id {bot_id} не найден.")
            return bot
