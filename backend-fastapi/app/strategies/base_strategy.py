from abc import ABC, abstractmethod
import logging
from typing import Dict, Any
import asyncio

class BaseStrategy(ABC):
    def __init__(self, bot_id: int, symbol: str, api_key: str, api_secret: str, testnet: bool = True):
        self.bot_id = bot_id
        self.symbol = symbol
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.stop_flag = False
        
    @abstractmethod
    async def execute_strategy(self):
        """Основной метод исполнения стратегии"""
        pass
    
    @abstractmethod
    async def stop_strategy(self):
        """Метод остановки стратегии"""
        pass
    