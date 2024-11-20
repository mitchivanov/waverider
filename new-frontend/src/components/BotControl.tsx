import React, { useState } from 'react';
import { botService } from '../services/api';
import { TradingParameters } from '../types';

const defaultParams: TradingParameters = {
  symbol: "BTCUSDT",
  asset_a_funds: 700,
  asset_b_funds: 0.01,
  grids: 10,
  deviation_threshold: 0.004,
  growth_factor: 0.5,
  use_granular_distribution: true,
  trail_price: true,
  only_profitable_trades: false
};

export const BotControl: React.FC = () => {
  const [params, setParams] = useState<TradingParameters>(defaultParams);
  const [isLoading, setIsLoading] = useState(false); // Adding loading state

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type, checked } = e.target;
    setParams(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : type === 'number' ? parseFloat(value) : value
    }));
  };

  const handleStart = async () => {
    try {
      setIsLoading(true);
      await botService.start(params);
      alert('Bot started successfully');
    } catch (error) {
      alert('Error starting bot');
    } finally {
      setIsLoading(false);
    }
  };

  const handleStop = async () => {
    try {
      setIsLoading(true);
      await botService.stop();
      alert('Bot stopped successfully');
    } catch (error) {
      console.error('Error stopping bot:', error);
      alert('Error stopping bot: ' + (error as Error).message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bot-control bg-gray-800 p-6 rounded-lg shadow-lg">
      <h2 className="text-2xl font-semibold text-white mb-4">Bot Control</h2>
      <form onSubmit={(e) => { e.preventDefault(); handleStart(); }}>
        <div className="form-grid grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="form-group">
            <label className="block text-gray-300 mb-2">Trading Pair:</label>
            <input
              type="text"
              name="symbol"
              value={params.symbol}
              onChange={handleInputChange}
              className="w-full px-3 py-2 bg-gray-700 text-white border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
            />
          </div>

          <div className="form-group">
            <label className="block text-gray-300 mb-2">Asset A Funds:</label>
            <input
              type="number"
              name="asset_a_funds"
              value={params.asset_a_funds}
              onChange={handleInputChange}
              className="w-full px-3 py-2 bg-gray-700 text-white border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
              min="0"
            />
          </div>

          <div className="form-group">
            <label className="block text-gray-300 mb-2">Asset B Funds:</label>
            <input
              type="number"
              name="asset_b_funds"
              value={params.asset_b_funds}
              onChange={handleInputChange}
              className="w-full px-3 py-2 bg-gray-700 text-white border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
              min="0"
              step="0.0001"
            />
          </div>

          <div className="form-group">
            <label className="block text-gray-300 mb-2">Number of Grids:</label>
            <input
              type="number"
              name="grids"
              value={params.grids}
              onChange={handleInputChange}
              className="w-full px-3 py-2 bg-gray-700 text-white border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
              min="1"
            />
          </div>

          <div className="form-group">
            <label className="block text-gray-300 mb-2">Deviation Threshold:</label>
            <input
              type="number"
              name="deviation_threshold"
              step="0.001"
              value={params.deviation_threshold}
              onChange={handleInputChange}
              className="w-full px-3 py-2 bg-gray-700 text-white border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
              min="0"
            />
          </div>

          <div className="form-group">
            <label className="block text-gray-300 mb-2">Growth Factor:</label>
            <input
              type="number"
              name="growth_factor"
              step="0.1"
              value={params.growth_factor}
              onChange={handleInputChange}
              className="w-full px-3 py-2 bg-gray-700 text-white border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
              min="0"
            />
          </div>

          <div className="form-group checkbox flex items-center space-x-2">
            <input
              type="checkbox"
              name="use_granular_distribution"
              checked={params.use_granular_distribution}
              onChange={handleInputChange}
              className="h-4 w-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
            />
            <label className="text-gray-300">Use Granular Distribution</label>
          </div>

          <div className="form-group checkbox flex items-center space-x-2">
            <input
              type="checkbox"
              name="trail_price"
              checked={params.trail_price}
              onChange={handleInputChange}
              className="h-4 w-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
            />
            <label className="text-gray-300">Trail Price</label>
          </div>

          <div className="form-group checkbox flex items-center space-x-2">
            <input
              type="checkbox"
              name="only_profitable_trades"
              checked={params.only_profitable_trades}
              onChange={handleInputChange}
              className="h-4 w-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
            />
            <label className="text-gray-300">Only Profitable Trades</label>
          </div>
        </div>

        <div className="button-group flex space-x-4 mt-4">
          <button 
            type="submit" 
            className={`start-button px-4 py-2 rounded-md text-white font-semibold ${isLoading ? 'bg-green-400 cursor-not-allowed' : 'bg-green-600 hover:bg-green-700'}`}
            disabled={isLoading}
          >
            {isLoading ? 'Starting...' : 'Start Bot'}
          </button>
          <button 
            type="button" 
            onClick={handleStop} 
            className={`stop-button px-4 py-2 rounded-md text-white font-semibold ${isLoading ? 'bg-red-400 cursor-not-allowed' : 'bg-red-600 hover:bg-red-700'}`}
            disabled={isLoading}
          >
            {isLoading ? 'Stopping...' : 'Stop Bot'}
          </button>
        </div>
      </form>
    </div>
  );
};
