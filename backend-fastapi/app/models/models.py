from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
import datetime

class BaseBot(SQLModel, table=True):
    """Базовая модель для всех типов ботов"""
    __tablename__ = "bots"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    type: str = Field(index=True)  # Тип стратегии: 'grid', 'other', и т.д.
    symbol: str
    api_key: str
    api_secret: str
    testnet: bool = Field(default=True)
    status: str = Field(default="inactive")
    
    # Метаданные
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    
    # Связи с конфигурациями стратегий
    grid_config: Optional["GridBotConfig"] = Relationship(back_populates="bot")
    #other_config: Optional["OtherBotConfig"] = Relationship(back_populates="bot")  # Связь с другой стратегией
    
    # Связи с другими таблицами
    active_orders: List["ActiveOrder"] = Relationship(back_populates="bot")
    trade_histories: List["TradeHistory"] = Relationship(back_populates="bot")
    order_histories: List["OrderHistory"] = Relationship(back_populates="bot")


class GridBotConfig(SQLModel, table=True):
    """Конфигурация для грид-бота"""
    __tablename__ = "grid_bot_configs"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    bot_id: int = Field(foreign_key="bots.id")
    asset_a_funds: float
    asset_b_funds: float
    grids: int
    deviation_threshold: float
    growth_factor: float
    use_granular_distribution: bool = Field(default=True)
    trail_price: bool = Field(default=True)
    only_profitable_trades: bool = Field(default=False)
    
    bot: Optional[BaseBot] = Relationship(back_populates="grid_config")


class ActiveOrder(SQLModel, table=True):
    """Модель активного ордера"""
    __tablename__ = "active_orders"
    
    order_id: str = Field(primary_key=True)
    bot_id: int = Field(foreign_key="bots.id")
    order_type: str = Field(index=True)
    is_initial: bool = Field(index=True)
    price: float
    quantity: float
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    
    bot: Optional[BaseBot] = Relationship(back_populates="active_orders")
    
    class Config:
        arbitrary_types_allowed = True


class TradeHistory(SQLModel, table=True):
    """Модель истории сделок"""
    __tablename__ = "trade_history"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    bot_id: int = Field(foreign_key="bots.id")
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
    
    bot: Optional[BaseBot] = Relationship(back_populates="trade_histories")
    
    class Config:
        json_encoders = {
            datetime.datetime: lambda v: v.isoformat()
        }
        arbitrary_types_allowed = True


class OrderHistory(SQLModel, table=True):
    """Модель истории ордеров"""
    __tablename__ = "order_history"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    bot_id: int = Field(foreign_key="bots.id")
    order_id: str = Field(index=True)
    order_type: str  # 'buy' или 'sell'
    is_initial: bool = Field(index=True)
    price: float
    quantity: float
    status: str  # 'OPEN', 'CLOSED', 'CANCELLED' и т.д.
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    
    bot: Optional[BaseBot] = Relationship(back_populates="order_histories")
    
    class Config:
        json_encoders = {
            datetime.datetime: lambda v: v.isoformat()
        }
        arbitrary_types_allowed = True


#class OtherBotConfig(SQLModel, table=True):
#    """Конфигурация для другой стратегии"""
#    __tablename__ = "other_bot_configs"
    
#    id: Optional[int] = Field(default=None, primary_key=True)
#    bot_id: int = Field(foreign_key="bots.id")
#    parameter_x: int
#    parameter_y: int
#    
#    bot: Optional[BaseBot] = Relationship(back_populates="other_config")



