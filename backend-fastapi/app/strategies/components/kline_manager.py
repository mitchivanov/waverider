import asyncio
import logging
import aiohttp
from typing import Optional, Callable, List
from models.models import TradeHistory, ActiveOrder
from manager import TradingBotManager

class KlineManager:
    """Модуль для получения данных Kline с Binance и передачи их через WebSocket."""

    def __init__(self, symbol: str, interval: str = '1m'):
        self.symbol = symbol.upper()
        self.interval = interval
        self.base_url = 'https://api.binance.com/api/v3/klines'
        self.running = False
        self.logger = logging.getLogger('kline_manager')

    async def fetch_kline_data(self, limit: int = 100) -> Optional[List[dict]]:
        """Получает последние данные Kline для указанного символа и интервала."""
        params = {
            'symbol': self.symbol,
            'interval': self.interval,
            'limit': limit  # Получаем последние свечи
        }
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(self.base_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data:
                            klines = []
                            for item in data:
                                kline = {
                                    'open_time': item[0],
                                    'open': float(item[1]),
                                    'high': float(item[2]),
                                    'low': float(item[3]),
                                    'close': float(item[4]),
                                    'volume': float(item[5]),
                                    'close_time': item[6],
                                    'quote_asset_volume': float(item[7]),
                                    'number_of_trades': item[8],
                                    'taker_buy_base_asset_volume': float(item[9]),
                                    'taker_buy_quote_asset_volume': float(item[10]),
                                }
                                klines.append(kline)
                            return klines
                    else:
                        self.logger.error(f"Не удалось получить данные Kline: статус {response.status}")
            except Exception as e:
                self.logger.error(f"Ошибка при получении данных Kline: {e}")
        return None

    async def start(self, broadcast_callback: Callable[[dict], asyncio.Future]):
        """Запускает процесс получения и передачи данных Kline."""
        self.running = True
        self.logger.info(f"KlineManager запущен для символа {self.symbol} с интервалом {self.interval}")
        while self.running:
            kline_data = await self.fetch_kline_data()
            if kline_data:
                for kline in kline_data:
                    await broadcast_callback(kline)
            await asyncio.sleep(self.get_sleep_interval())

    def get_sleep_interval(self) -> int:
        """Определяет паузу между запросами в зависимости от интервала."""
        interval_mapping = {
            '1m': 60,
            '3m': 180,
            '5m': 300,
            '15m': 900,
            '30m': 1800,
            '1h': 3600,
            '2h': 7200,
            '4h': 14400,
            '6h': 21600,
            '12h': 43200,
            '1d': 86400,
            '3d': 259200,
            '1w': 604800,
            '1M': 2592000,
        }
        return interval_mapping.get(self.interval, 60)

    async def stop(self):
        """Останавливает процесс получения данных Kline."""
        self.running = False
        self.logger.info(f"KlineManager остановлен для символа {self.symbol}")