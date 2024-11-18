import logging
from typing import Dict
from datetime import datetime

from sqlalchemy.future import select
from sqlalchemy import update, delete

from app.database import async_session
from app.models.models import ActiveOrder, TradeHistory

class DatabaseManager:
    """Модуль для работы с базой данных"""

    def __init__(self):
        pass

    async def add_active_order(self, order_data: Dict):
        """Добавляет активный ордер в базу данных"""
        try:
            async with async_session() as session:
                active_order = ActiveOrder(
                    order_id=order_data["order_id"],
                    order_type=order_data["order_type"],
                    price=order_data["price"],
                    quantity=order_data["quantity"],
                    created_at=datetime.datetime.utcnow()
                )
                session.add(active_order)
                await session.commit()
                logging.info(f"Активный ордер добавлен в БД: {order_data['order_id']}")
        except Exception as e:
            logging.error(f"Ошибка при добавлении активного ордера в БД: {e}")

    async def remove_active_order(self, order_id: str):
        """Удаляет активный ордер из базы данных"""
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(ActiveOrder).where(ActiveOrder.order_id == order_id)
                )
                order = result.scalar_one_or_none()
                if order:
                    await session.delete(order)
                    await session.commit()
                    logging.info(f"Активный ордер удален из БД: {order_id}")
                else:
                    logging.warning(f"Активный ордер не найден в БД: {order_id}")
        except Exception as e:
            logging.error(f"Ошибка при удалении активного ордера из БД: {e}")

    async def add_trade_to_history(self, trade_data: Dict):
        """Добавляет завершенную сделку в историю"""
        try:
            async with async_session() as session:
                trade = TradeHistory(
                    buy_price=trade_data["buy_price"],
                    sell_price=trade_data["sell_price"],
                    quantity=trade_data["quantity"],
                    profit=trade_data["profit"],
                    profit_asset=trade_data["profit_asset"],
                    status=trade_data["status"],
                    trade_type=trade_data["trade_type"],
                    executed_at=datetime.datetime.utcnow()
                )
                session.add(trade)
                await session.commit()
                logging.info(f"Сделка добавлена в историю: {trade.id}")
        except Exception as e:
            logging.error(f"Ошибка при добавлении сделки в историю: {e}")

    async def update_trade_in_history(self, trade_id: int, updated_data: Dict):
        """Обновляет существующую сделку в истории"""
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(TradeHistory).where(TradeHistory.id == trade_id)
                )
                trade = result.scalar_one_or_none()
                if trade:
                    for key, value in updated_data.items():
                        setattr(trade, key, value)
                    await session.commit()
                    logging.info(f"Сделка обновлена в истории: {trade_id}")
                else:
                    logging.warning(f"Сделка не найдена в истории: {trade_id}")
        except Exception as e:
            logging.error(f"Ошибка при обновлении сделки в истории: {e}") 