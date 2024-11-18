import asyncio
import logging
from binance import AsyncClient, BinanceSocketManager
from typing import Optional

class PriceManager:
    """Модуль для работы с ценами и WebSocket"""

    def __init__(self, symbol: str, on_price_update):
        self.symbol = symbol.lower()
        self.on_price_update = on_price_update  # Callback функция при обновлении цены
        self.client: Optional[AsyncClient] = None
        self.bsm: Optional[BinanceSocketManager] = None
        self.price_task: Optional[asyncio.Task] = None

    async def start_price_updates(self):
        """Запускает обновление цены через WebSocket"""
        self.client = await AsyncClient.create()
        self.bsm = BinanceSocketManager(self.client)
        socket = self.bsm.symbol_ticker_socket(self.symbol)
        self.price_task = asyncio.create_task(self._listen_price(socket))
        logging.info(f"Запущен WebSocket для {self.symbol}")

    async def _listen_price(self, socket):
        """Прослушивает поток ценовых обновлений"""
        try:
            async with socket as s:
                async for msg in s:
                    if 'c' in msg:
                        current_price = float(msg['c'])
                        logging.debug(f"Обновленная цена {self.symbol}: {current_price}")
                        await self.on_price_update(current_price)
        except Exception as e:
            logging.error(f"Ошибка в WebSocket для {self.symbol}: {e}")
            await asyncio.sleep(5)
            await self.start_price_updates()

    async def stop_price_updates(self):
        """Останавливает обновление цены"""
        if self.bsm:
            self.bsm.stop_socket(self.symbol)
        if self.price_task:
            self.price_task.cancel()
            try:
                await self.price_task
            except asyncio.CancelledError:
                logging.info(f"Таск обновления цены для {self.symbol} остановлен.")
        if self.client:
            await self.client.close_connection()
            logging.info(f"Клиент Binance для {self.symbol} закрыт.") 