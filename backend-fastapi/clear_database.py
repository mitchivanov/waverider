import asyncio
import sys
from sqlalchemy import delete
from app.database import async_session, init_db
from app.models.models import BaseBot, ActiveOrder, TradeHistory, OrderHistory

async def clear_database():
    """Очищает все таблицы в базе данных."""
    try:
        await init_db()
        async with async_session() as session:
            # Сначала удаляем записи из зависимых таблиц
            await session.execute(delete(ActiveOrder))
            await session.execute(delete(TradeHistory))
            await session.execute(delete(OrderHistory))
            # Затем удаляем записи из основной таблицы
            await session.execute(delete(BaseBot))
            await session.commit()
        print("База данных успешно очищена")
    except Exception as e:
        print(f"Произошла ошибка при очистке базы данных: {e}") 

if __name__ == "__main__":
    asyncio.run(clear_database())
