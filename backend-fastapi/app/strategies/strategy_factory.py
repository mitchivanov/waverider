# backend-fastapi/app/strategies/strategy_factory.py
from typing import Type
from .base_strategy import BaseStrategy
from .gridstrat import GridStrategy
from .sellbot_strategy import SellBot

def get_strategy_class(strategy_type: str) -> Type[BaseStrategy]:
    strategies = {
        'grid': GridStrategy,
        'sellbot': SellBot
    }
    
    if strategy_type not in strategies:
        raise ValueError(f"Unknown strategy type: {strategy_type}")
        
    return strategies[strategy_type]