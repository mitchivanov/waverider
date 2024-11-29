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
from models.models import ActiveOrder, TradeHistory, OrderHistory
import asyncio
from sqlalchemy import delete
from models.models import TradingParameters
import json
from starlette.websockets import WebSocketState

from kline_manager import KlineManager

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

# Хранилище KlineManager по WebSocket соединениям
kline_managers: Dict[int, KlineManager] = {}
kline_tasks: Dict[int, asyncio.Task] = {}


@app.on_event("startup")
async def startup_event():
    await init_db()

@app.post("/api/bot/{bot_id}/start")
async def start_bot(bot_id: int, params: TradingParameters):
    try:
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
        
        await TradingBotManager.start_bot(bot_id, parameters)
        return {"status": "Bot started successfully", "bot_id": bot_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/bot/{bot_id}/stop")
async def stop_bot(bot_id: int):
    try:
        await TradingBotManager.stop_bot(bot_id)
        return {"status": "Bot stopped successfully", "bot_id": bot_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, Dict[str, WebSocket]] = {}

    async def connect(self, websocket: WebSocket, bot_id: int, connection_id: str):
        await websocket.accept()
        if bot_id not in self.active_connections:
            self.active_connections[bot_id] = {}
        self.active_connections[bot_id][connection_id] = websocket

    def disconnect(self, websocket: WebSocket, bot_id: int, connection_id: str):
        if bot_id in self.active_connections:
            if connection_id in self.active_connections[bot_id]:
                del self.active_connections[bot_id][connection_id]
            if not self.active_connections[bot_id]:
                del self.active_connections[bot_id]

    async def broadcast(self, bot_id: int, message: dict):
        if bot_id in self.active_connections:
            disconnected = []
            for connection_id, websocket in self.active_connections[bot_id].items():
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    ws_logger.error(f"Ошибка при отправке сообщения для бота {bot_id}, соединение {connection_id}: {e}")
                    disconnected.append((connection_id, websocket))
            for connection_id, websocket in disconnected:
                self.disconnect(websocket, bot_id, connection_id)

manager = ConnectionManager()

@app.websocket("/ws/{bot_id}")
async def websocket_endpoint(websocket: WebSocket, bot_id: int):
    await manager.connect(websocket, bot_id)
    ws_logger.info(f"WebSocket подключен: {websocket.client} для бота {bot_id}")
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

                if websocket.client_state == WebSocketState.CONNECTED:
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
                parameters = await TradingBotManager.get_current_parameters(bot_id)
                if parameters is None:
                    await asyncio.sleep(1)
                    continue

                # Получение последних свечей
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
                    await manager.broadcast(bot_id, candle_data)
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
                    if parameters.get("current_price") is not None:
                        ohlc["close"] = parameters["current_price"]
                        ohlc["high"] = max(ohlc["high"], parameters["current_price"])
                        ohlc["low"] = min(ohlc["low"], parameters["current_price"])
                        # ohlc["volume"] += trade_volume  # Обновите объем при необходимости
                    else:
                        ws_logger.warning("current_price is None, не обновляем свечу")

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
                await manager.broadcast(bot_id, status_update)

                # Отправляем данные об ордерах и сделках
                active_orders_data = [
                    {
                        "order_id": order.order_id,
                        "order_type": order.order_type,
                        "isInitial": order.isInitial,
                        "price": order.price,
                        "quantity": order.quantity,
                        "created_at": order.created_at.isoformat()
                    }
                    for order in await TradingBotManager.get_active_orders_list(bot_id)
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
                        "buy_order_id": trade.buy_order_id,
                        "sell_order_id": trade.sell_order_id,
                        "executed_at": trade.executed_at.isoformat()
                    }
                    for trade in await TradingBotManager.get_all_trades_list(bot_id)
                ]

                order_history_data = [
                    {
                        "order_id": order.order_id,
                        "order_type": order.order_type,
                        "isInitial": order.isInitial,
                        "price": order.price,
                        "quantity": order.quantity,
                        "status": order.status,
                        "created_at": order.created_at.isoformat(),
                        "updated_at": order.updated_at.isoformat()
                    }
                    for order in await TradingBotManager.get_order_history_list(bot_id)
                ]

                await manager.broadcast(bot_id, {"type": "active_orders_data", "payload": active_orders_data})

                await manager.broadcast(bot_id, {"type": "all_trades_data", "payload": all_trades_data})

                await manager.broadcast(bot_id, {"type": "order_history_data", "payload": order_history_data})

                await asyncio.sleep(1)
            except TypeError as e:
                ws_logger.error(f"TypeError при отправке обновлений: {e}", exc_info=True)
                # Не разрываем WebSocket, продолжаем работу
            except Exception as e:
                ws_logger.error(f"Ошибка при отправке обновлений: {e}", exc_info=True)
                break
    except WebSocketDisconnect:
        ws_logger.info(f"WebSocket отключен: {websocket.client}")
        manager.disconnect(websocket, bot_id)
    except Exception as e:
        ws_logger.error(f"Ошибка WebSocket: {e}", exc_info=True)
    finally:
        ws_logger.info(f"WebSocket соединение закрыто: {websocket.client}")
        manager.disconnect(websocket, bot_id)
        # Останавливаем KlineManager для этого соединения
        if connection_id in kline_managers:
            await kline_managers[connection_id].stop()
            del kline_managers[connection_id]
        if connection_id in kline_tasks:
            kline_tasks[connection_id].cancel()
            del kline_tasks[connection_id]

@app.on_event("shutdown")
async def shutdown_event():
    # Останавливаем все активные боты
    for bot_id in list(TradingBotManager._bots.keys()):
        try:
            await TradingBotManager.stop_bot(bot_id)
        except Exception as e:
            logging.error(f"Error stopping bot {bot_id} during shutdown: {e}")
    
    # Останавливаем все KlineManager
    for manager_instance in kline_managers.values():
        await manager_instance.stop()
    for task in kline_tasks.values():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
async def clear_database(bot_id):
    """Очищает таблицы в базе данных для конкретного бота или все таблицы."""
    async with async_session() as session:
        try:
            if bot_id is not None:
                # Очищаем данные только для конкретного бота
                await session.execute(delete(ActiveOrder).where(ActiveOrder.bot_id == bot_id))
                await session.execute(delete(TradeHistory).where(TradeHistory.bot_id == bot_id))
                await session.execute(delete(OrderHistory).where(OrderHistory.bot_id == bot_id))
            else:
                # Очищаем все данные
                await session.execute(delete(ActiveOrder))
                await session.execute(delete(TradeHistory))
                await session.execute(delete(OrderHistory))
            await session.commit()
            logging.info(f"База данных успешно очищена{f' для бота {bot_id}' if bot_id else ''}")
        except Exception as e:
            await session.rollback()
            logging.error(f"Ошибка при очистке базы данных: {e}")
            raise

@app.get("/api/bots")
async def get_bots():
    """Возвращает список всех активных ботов"""
    try:
        bots = await TradingBotManager.get_all_bots()
        return {"bots": [
            {
                "id": bot_id,
                "status": await TradingBotManager.get_bot_status(bot_id),
                "uptime": await TradingBotManager.get_bot_uptime(bot_id)
            }
            for bot_id in bots
        ]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/bot/{bot_id}")
async def delete_bot(bot_id: int):
    """Останавливает бота и удаляет его данные из базы"""
    try:
        await TradingBotManager.stop_bot(bot_id)
        await clear_database(bot_id)
        return {"status": "Bot deleted successfully", "bot_id": bot_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

