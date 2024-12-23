# backend-fastapi/app/strategies/strategy_factory.py
from typing import Type
from app.strategies.base_strategy import BaseStrategy
from app.strategies.gridstrat import GridStrategy
from app.strategies.sellbot_strategy import SellBot
from app.strategies.indexfundstrat import IndexFundStrategy

def get_strategy_class(strategy_type: str) -> Type[BaseStrategy]:
    strategies = {
        'grid': GridStrategy,
        'sellbot': SellBot,
        'indexfund': IndexFundStrategy
    }
    
    if strategy_type not in strategies:
        raise ValueError(f"Unknown strategy type: {strategy_type}")
        
    return strategies[strategy_type]