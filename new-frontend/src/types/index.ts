export interface BaseTradingParameters {
  type: 'grid' | 'another';
  api_key: string;
  api_secret: string;
  testnet: boolean;
}

export interface Bot {
  id: number;
  type: string;
  symbol: string;
  status: string;
  uptime: number;
}

export interface GridTradingParameters extends BaseTradingParameters {
  type: 'grid';
  baseAsset: string;    // Например "BTC"
  quoteAsset: string;
  asset_a_funds: number;
  asset_b_funds: number;
  grids: number;
  deviation_threshold: number;
  growth_factor: number;
  use_granular_distribution: boolean;
  trail_price: boolean;
  only_profitable_trades: boolean;
}

export interface AnotherTradingParameters extends BaseTradingParameters {
  type: 'another';
  parameter_x: number;
  parameter_y: number;
}

export type TradingParameters = GridTradingParameters | AnotherTradingParameters;

export interface PriceData {
  time: string; // ISO format date
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface ActiveOrder {
  order_id: string;
  order_type: 'buy' | 'sell';
  isInitial: boolean;
  price: number;
  quantity: number;
  created_at: string;
}

export interface TradeHistory {
  buy_price: number;
  sell_price: number;
  quantity: number;
  profit: number;
  profit_asset: string;
  status: string;
  trade_type: string;
  buy_order_id: string;
  sell_order_id: string;
  executed_at?: string;
}

export interface OrderHistory {
  order_id: string;
  order_type: string;
  isInitial: boolean;
  price: number;
  quantity: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface BotStatus {
  status: 'active' | 'stopped';
  current_price: number | null;
  deviation: number | null;
  
  // Realized profits
  realized_profit_a: number;
  realized_profit_b: number;
  total_profit_usdt: number;
  
  // Unrealized profits
  unrealized_profit_a: number;
  unrealized_profit_b: number;
  unrealized_profit_usdt: number;
  
  // Counts
  active_orders_count: number;
  completed_trades_count: number;
  
  running_time: string | null;
  initial_parameters: TradingParameters;
}

export interface Notification {
  id: string;
  type: 'trade' | 'error' | 'info' | 'new_trade';
  message: string;
  details?: Record<string, any>;
  timestamp: Date;
  payload?: {
    trade_type: 'BUY_SELL' | 'SELL_BUY';
    buy_price: number;
    sell_price: number;
    quantity: number;
    symbol: string;
  };
}

export interface WebSocketNotification {
  bot_id: number;
  notification_type: string;
  type: 'notification';
  payload: {
    notification_type: string;
    trade_type: string;
    buy_price: number;
    sell_price: number;
    quantity: number;
    symbol: string;
  };
}