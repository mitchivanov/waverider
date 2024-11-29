from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
import datetime

class TradingParameters(SQLModel):
    """Базовая модель для параметров стратегий."""
    id: Optional[int] = Field(default=None, primary_key=True)

class GridTradingParameters(TradingParameters, table=True):
    symbol: str = "BTCUSDT"
    asset_a_funds: float = 1000.0
    asset_b_funds: float = 0.1
    grids: int = 20
    deviation_threshold: float = 0.02
    trail_price: bool = True
    only_profitable_trades: bool = False
    growth_factor: float = 0.5
    use_granular_distribution: bool = True

class AnotherStrategyParameters(TradingParameters, table=True):
    # Пример дополнительных параметров для другой стратегии
    parameter_x: float
    parameter_y: int
    # Добавьте остальные необходимые поля

class Bot(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    type: str = Field(index=True)  # Тип стратегии, например, 'grid', 'another'
    parameters_id: int = Field(foreign_key="tradingparameters.id")
    status: str = Field(default="inactive")  # Например: 'active', 'inactive'
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    parameters: TradingParameters = Relationship()

    active_orders: List["ActiveOrder"] = Relationship(back_populates="bot")
    trade_histories: List["TradeHistory"] = Relationship(back_populates="bot")
    order_histories: List["OrderHistory"] = Relationship(back_populates="bot")

class ActiveOrder(SQLModel, table=True):
    order_id: str = Field(primary_key=True)
    bot_id: int = Field(foreign_key="bot.id")
    order_type: str = Field(index=True)
    isInitial: bool = Field(index=True)
    price: float
    quantity: float
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    bot: Bot = Relationship(back_populates="active_orders")

    class Config:
        table_name = "active_order"
        arbitrary_types_allowed = True

class TradeHistory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    bot_id: int = Field(foreign_key="bot.id")
    buy_price: Optional[float]
    sell_price: Optional[float]
    quantity: float
    profit: float
    profit_asset: Optional[str] = Field(default=None)
    status: str = Field(default='OPEN')
    trade_type: str = Field(default='LIMIT')
    buy_order_id: Optional[str] = Field(default=None)
    sell_order_id: Optional[str] = Field(default=None)
    executed_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    bot: Bot = Relationship(back_populates="trade_histories")

    class Config:
        table_name = "trade_history"
        json_encoders = {
            datetime.datetime: lambda v: v.isoformat()
        }
        arbitrary_types_allowed = True

class OrderHistory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    bot_id: int = Field(foreign_key="bot.id")
    order_id: str = Field(index=True)
    order_type: str  # 'buy' или 'sell'
    isInitial: bool = Field(index=True)
    price: float
    quantity: float
    status: str  # 'OPEN', 'CLOSED', 'CANCELLED' и т.д.
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    bot: Bot = Relationship(back_populates="order_histories")

    class Config:
        table_name = "order_history"
        json_encoders = {
            datetime.datetime: lambda v: v.isoformat()
        }
        arbitrary_types_allowed = True



