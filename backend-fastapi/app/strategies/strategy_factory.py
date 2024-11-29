# backend-fastapi/app/strategies/strategy_factory.py
from typing import Type
from .base_strategy import BaseStrategy
from .gridstrat import GridStrategy

def get_strategy_class(strategy_type: str) -> Type[BaseStrategy]:
    if strategy_type == 'grid':
        return GridStrategy
    else:
        raise ValueError(f"Неизвестный тип стратегии: {strategy_type}")