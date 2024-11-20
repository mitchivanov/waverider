export interface TradingParameters {
  symbol: string;
  asset_a_funds: number;
  asset_b_funds: number;
  grids: number;
  deviation_threshold: number;
  trail_price: boolean;
  only_profitable_trades: boolean;
  growth_factor: number;
  use_granular_distribution: boolean;
}

// Добавьте другие интерфейсы по необходимости 