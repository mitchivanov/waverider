from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from typing import Dict, List, Set, Optional, Callable
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
import json
from starlette.websockets import WebSocketState

from strategies.components.kline_manager import KlineManager

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

# Хранилище KlineManager по WebSocket соединениям
kline_managers: Dict[int, KlineManager] = {}
kline_tasks: Dict[int, asyncio.Task] = {}


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
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                ws_logger.error(f"Ошибка при отправке сообщения: {e}")
                disconnected.append(connection)
        for connection in disconnected:
            self.disconnect(connection)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    ws_logger.info(f"WebSocket подключен: {websocket.client}")
    connection_id = id(websocket)  # Уникальный идентификатор для соединения

    try:
        # Ожидаем получения параметров подписки от клиента
        subscription_message = await websocket.receive_json()
        symbol = subscription_message.get("symbol", "BTCUSDT")  # Символ по умолчанию
        interval = subscription_message.get("interval", "1m")   # Интервал по умолчанию

        # Инициализация KlineManager для этого соединения
        async def broadcast_kline(kline: dict):
            message = {
                "type": "kline_data",
                "symbol": symbol,
                "data": kline
            }
            await websocket.send_json(message)

        kline_manager = KlineManager(symbol=symbol, interval=interval)
        kline_managers[connection_id] = kline_manager
        kline_task = asyncio.create_task(kline_manager.start(broadcast_kline))
        kline_tasks[connection_id] = kline_task

        # Получение и отправка исторических свечей
        historical_klines = await kline_manager.fetch_kline_data(limit=100)
        if historical_klines:
            historical_message = {
                "type": "historical_kline_data",
                "symbol": symbol,
                "data": historical_klines
            }
            await websocket.send_json(historical_message)

        # Инициализация переменных для свечей
        last_candle_time = None
        ohlc = {
            "open": 0.0,
            "high": 0.0,
            "low": float('inf'),
            "close": 0.0,
            "volume": 0.0
        }
        candle_interval = 15  # Интервал свечи в секундах (например, 15 секунд)

        while True:
            try:
                
                # WebSocketState.CLOSED (0): Соединение закрыто.
                # WebSocketState.CONNECTING (1): Соединение устанавливается.
                # WebSocketState.OPEN (2): Соединение открыто и активно.

                # Проверяем наличие новых сообщений от клиента
                if websocket.client_state == WebSocketState.DISCONNECTED:
                    break

                if websocket.client_state == WebSocketState.OPEN:
                    try:
                        message = await asyncio.wait_for(websocket.receive_json(), timeout=0.1)
                        msg_type = message.get("type")
                        if msg_type == "change_interval":
                            new_interval = message.get("interval")
                            if new_interval and new_interval != interval:
                                interval = new_interval
                                # Останавливаем текущий KlineManager
                                await kline_managers[connection_id].stop()
                                kline_tasks[connection_id].cancel()

                                # Инициализируем новый KlineManager с новым интервалом
                                kline_manager = KlineManager(symbol=symbol, interval=interval)
                                kline_managers[connection_id] = kline_manager
                                kline_task = asyncio.create_task(kline_manager.start(broadcast_kline))
                                kline_tasks[connection_id] = kline_task

                                # Получаем новые исторические данные для нового интервала
                                historical_klines = await kline_manager.fetch_kline_data(limit=100)
                                if historical_klines:
                                    historical_message = {
                                        "type": "historical_kline_data",
                                        "symbol": symbol,
                                        "data": historical_klines
                                    }
                                    await websocket.send_json(historical_message)

                                ws_logger.info(f"Интервал изменен на {new_interval} для соединения {connection_id}")
                    except asyncio.TimeoutError:
                        pass  # Нет новых сообщений

                # Основной цикл для отправки других данных (например, статуса, ордеров и т.д.)
                parameters = await TradingBotManager.get_current_parameters()
                if parameters is None:
                    await asyncio.sleep(1)
                    continue
                
########################################################################################################################################################################    
                # Получеие последних свечей
                
                
                current_timestamp = int(datetime.datetime.utcnow().timestamp())
                candle_time = current_timestamp - (current_timestamp % candle_interval)

                # Инициализация начального времени свечи
                if last_candle_time is None:
                    last_candle_time = candle_time

                # Проверка, нужно ли закрывать текущую свечу и открыть новую
                if candle_time > last_candle_time:
                    # Отправка завершенной свечи
                    candle_data = {
                        "type": "candlestick_update",
                        "symbol": parameters["initial_parameters"]["symbol"],
                        "data": {
                            "time": last_candle_time,
                            "open": ohlc["open"],
                            "high": ohlc["high"],
                            "low": ohlc["low"],
                            "close": ohlc["close"],
                            "volume": ohlc["volume"]
                        }
                    }
                    await manager.broadcast(candle_data)
                    ws_logger.debug(f"Отправлено candle_data: {json.dumps(candle_data)}")

                    # Сброс OHLV для новой свечи
                    ohlc = {
                        "open": parameters["current_price"],
                        "high": parameters["current_price"],
                        "low": parameters["current_price"],
                        "close": parameters["current_price"],
                        "volume": 0.0  # Добавьте реализацию объема, если необходимо
                    }
                    last_candle_time = candle_time
                else:
                    # Обновление текущей свечи
                    ohlc["close"] = parameters["current_price"]
                    ohlc["high"] = max(ohlc["high"], parameters["current_price"])
                    ohlc["low"] = min(ohlc["low"], parameters["current_price"])
                    # ohlc["volume"] += trade_volume  # Обновите объем при необходимости    




########################################################################################################################################################################    




                # Отправляем статус
                status_update = {
                    "type": "status_update",
                    "data": {
                        "status": parameters["status"],
                        "current_price": parameters["current_price"],
                        "deviation": parameters["deviation"],
                        
                        "realized_profit_a": parameters["realized_profit_a"],
                        "realized_profit_b": parameters["realized_profit_b"],
                        "total_profit_usdt": parameters["total_profit_usdt"],
                        
                        "active_orders_count": parameters["active_orders_count"],
                        "completed_trades_count": parameters["completed_trades_count"],
                        
                        "running_time": parameters["running_time"],

                        "unrealized_profit_a": parameters["unrealized_profit_a"],
                        "unrealized_profit_b": parameters["unrealized_profit_b"],
                        "unrealized_profit_usdt": parameters["unrealized_profit_usdt"],
                        
                        "initial_parameters": parameters["initial_parameters"],
                    }
                }
                await manager.broadcast(status_update)
                ws_logger.debug(f"Отправлено status_update: {json.dumps(status_update)}")

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
                ws_logger.debug(f"Отправлено active_orders_data: {json.dumps(active_orders_data)}")
                
                await manager.broadcast({"type": "all_trades_data", "payload": all_trades_data})
                ws_logger.debug(f"Отправлено all_trades_data: {json.dumps(all_trades_data)}")

                await asyncio.sleep(1)
            except Exception as e:
                ws_logger.error(f"Ошибка при отправке обновлений: {e}", exc_info=True)
                break
    except WebSocketDisconnect:
        ws_logger.info(f"WebSocket отключен: {websocket.client}")
        manager.disconnect(websocket)
    except Exception as e:
        ws_logger.error(f"Ошибка WebSocket: {e}", exc_info=True)
    finally:
        ws_logger.info(f"WebSocket соединение закрыто: {websocket.client}")
        manager.disconnect(websocket)
        # Останавливаем KlineManager для этого соединения
        if connection_id in kline_managers:
            await kline_managers[connection_id].stop()
            del kline_managers[connection_id]
        if connection_id in kline_tasks:
            kline_tasks[connection_id].cancel()
            del kline_tasks[connection_id]

@app.on_event("shutdown")
async def shutdown_event():
    if "bot" in bot_instance:
        try:
            bot_instance["bot"].stop()
            await bot_instance["bot"].close()
        except Exception as e:
            logging.error(f"Error during shutdown: {e}")
    
    # Останавливаем все KlineManager
    for manager_instance in kline_managers.values():
        await manager_instance.stop()
    for task in kline_tasks.values():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
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
