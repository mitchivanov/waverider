from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from typing import Dict, List, Set
import logging
import uvicorn
from gridstrat import GridStrategy
from fastapi.middleware.cors import CORSMiddleware
from database import init_db
import datetime
from manager import TradingBotManager
from database import async_session
from sqlalchemy.future import select
from models.models import ActiveOrder, TradeHistory
import asyncio
from sqlalchemy import delete
from models.models import TradingParameters


# Отключаем ненужные логи
logging.getLogger('websockets').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)
logging.getLogger('aiohttp').setLevel(logging.ERROR)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

# Создаем логгер для websocket
ws_logger = logging.getLogger('websocket')
ws_logger.setLevel(logging.DEBUG)

router = APIRouter()
active_connections: Set[WebSocket] = set()


app = FastAPI(title="Grid Trading Bot")
app.include_router(router)


# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Store bot instance
bot_instance: Dict[str, GridStrategy] = {}


@app.on_event("startup")
async def startup_event():
    await init_db()

@app.post("/api/bot/start")
async def start_bot(params: TradingParameters):
    try:
        await clear_database()
        
        parameters = {
            "symbol": params.symbol,
            "asset_a_funds": params.asset_a_funds,
            "asset_b_funds": params.asset_b_funds,
            "grids": params.grids,
            "deviation_threshold": params.deviation_threshold,
            "growth_factor": params.growth_factor,
            "use_granular_distribution": params.use_granular_distribution,
            "trail_price": params.trail_price,
            "only_profitable_trades": params.only_profitable_trades
        }
        
        await TradingBotManager.start_bot(parameters)
        return {"status": "Bot started successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/bot/stop")
async def stop_bot():
    try:
        await TradingBotManager.stop_bot()
        return {"status": "Bot stopped successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except WebSocketDisconnect:
                await self.disconnect(connection)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    ws_logger.info(f"WebSocket подключен: {websocket.client}")
    try:
        while True:
            try:
                parameters = await TradingBotManager.get_current_parameters()
                if parameters is None:
                    ws_logger.warning("Параметры не получены: бот не запущен")
                    await asyncio.sleep(1)
                    continue
                    
                
                status = parameters["status"]
                current_price = parameters["current_price"]
                deviation = parameters["deviation"]
                
                realized_profit_a = parameters["realized_profit_a"]
                realized_profit_b = parameters["realized_profit_b"]
                total_profit_usdt = parameters["total_profit_usdt"]
                
                active_orders_count = parameters["active_orders_count"]
                completed_trades_count = parameters["completed_trades_count"]
                
                unrealized_profit_a = parameters["unrealized_profit_a"]
                unrealized_profit_b = parameters["unrealized_profit_b"]
                unrealized_profit_usdt = parameters["unrealized_profit_usdt"]
                
                running_time = parameters["running_time"]
                
                initial_parameters = parameters["initial_parameters"]
                # Отправляем статус
                status_update = {
                    "type": "status_update",
                    "data": {
                        "status": status,
                        "current_price": current_price,
                        "deviation": deviation,
                        
                        "realized_profit_a": realized_profit_a,
                        "realized_profit_b": realized_profit_b,
                        "total_profit_usdt": total_profit_usdt,
                        
                        "active_orders_count": active_orders_count,
                        "completed_trades_count": completed_trades_count,
                        
                        "running_time": running_time,

                        "unrealized_profit_a": unrealized_profit_a,
                        "unrealized_profit_b": unrealized_profit_b,
                        "unrealized_profit_usdt": unrealized_profit_usdt,
                        
                        "initial_parameters": initial_parameters,
                    }
                }
                ws_logger.debug(f"Отправка status_update: {status_update}")
                await manager.broadcast(status_update)

                # Отправляем данные об ордерах и сделках
                active_orders_data = [
                    {
                        "order_id": order.order_id,
                        "order_type": order.order_type,
                        "price": order.price,
                        "quantity": order.quantity,
                        "created_at": order.created_at.isoformat()
                    }
                    for order in await TradingBotManager.get_active_orders_list()
                ]
                ws_logger.debug(f"Отправка active_orders_data: {len(active_orders_data)} ордеров")

                all_trades_data = [
                    {
                        "buy_price": trade.buy_price,
                        "sell_price": trade.sell_price,
                        "quantity": trade.quantity,
                        "profit": trade.profit,
                        "profit_asset": trade.profit_asset,
                        "status": trade.status,
                        "trade_type": trade.trade_type,
                        "executed_at": trade.executed_at.isoformat()
                    }
                    for trade in await TradingBotManager.get_all_trades_list()
                ]

                await manager.broadcast({"type": "active_orders_data", "payload": active_orders_data})
                await manager.broadcast({"type": "all_trades_data", "payload": all_trades_data})

                await asyncio.sleep(1)
            except Exception as e:
                ws_logger.error(f"Ошибка при отправке обновлений: {e}", exc_info=True)
                break
    except WebSocketDisconnect:
        ws_logger.info(f"WebSocket отключен: {websocket.client}")
        manager.disconnect(websocket)
    finally:
        ws_logger.info(f"WebSocket соединение закрыто: {websocket.client}")
        manager.disconnect(websocket)

@app.on_event("shutdown")
async def shutdown_event():
    if "bot" in bot_instance:
        try:
            bot_instance["bot"].stop()
            await bot_instance["bot"].close()
        except Exception as e:
            logging.error(f"Error during shutdown: {e}")

async def clear_database():
    """Очищает все таблицы в базе данных."""
    async with async_session() as session:
        try:
            # Очищаем таблицу активных ордеров
            await session.execute(delete(ActiveOrder))
            # Очищаем таблицу истории торгов
            await session.execute(delete(TradeHistory))
            await session.commit()
            logging.info("База данных успешно очищена")
        except Exception as e:
            await session.rollback()
            logging.error(f"Ошибка при очистке базы данных: {e}")
            raise

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
