import React, { useState } from 'react';
import { botService } from '../services/api';
import { GridTradingParameters, AnotherTradingParameters } from '../types';
import { GridBotForm } from './GridBotForm';

const defaultGridParams: GridTradingParameters = {
  type: 'grid',
  symbol: "BTCUSDT",
  asset_a_funds: 5000,
  asset_b_funds: 0.05,
  grids: 10,
  deviation_threshold: 0.004,
  growth_factor: 0.5,
  use_granular_distribution: true,
  trail_price: true,
  only_profitable_trades: false,
  api_key: '',
  api_secret: '',
  testnet: true
};

const defaultAnotherParams: AnotherTradingParameters = {
  type: 'another',
  parameter_x: 0,
  parameter_y: 0,
  api_key: '',
  api_secret: '',
  testnet: true
};

export const BotControl: React.FC = () => {
  const [botType, setBotType] = useState<'grid' | 'another'>('grid');
  const [params, setParams] = useState<GridTradingParameters | AnotherTradingParameters>(defaultGridParams);
  const [isLoading, setIsLoading] = useState(false);
  const [isBotRunning, setIsBotRunning] = useState(false);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target as HTMLInputElement;
    setParams(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? (e.target as HTMLInputElement).checked 
            : type === 'number' ? parseFloat(value) 
            : value
    }));
  };

  const handleBotTypeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newType = e.target.value as 'grid' | 'another';
    setBotType(newType);
    setParams(newType === 'grid' ? defaultGridParams : defaultAnotherParams);
  };

  const handleStart = async () => {
    try {
      setIsLoading(true);
      await botService.start(params);
      alert('Bot started successfully');
      setIsBotRunning(true);
    } catch (error) {
      alert('Error starting the bot');
    } finally {
      setIsLoading(false);
    }
  };

  const handleStop = async () => {
    try {
      setIsLoading(true);
      await botService.stop();
      alert('Bot stopped successfully');
      setIsBotRunning(false);
    } catch (error) {
      console.error('Error stopping the bot:', error);
      alert('Error stopping the bot: ' + (error as Error).message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bot-control bg-gray-800 p-6 rounded-lg shadow-lg">
      <h2 className="text-2xl font-semibold text-white mb-4">Bot Control</h2>
      <form onSubmit={(e) => { e.preventDefault(); handleStart(); }}>
        <div className="form-grid grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="form-group col-span-2">
            <label className="block text-gray-300 mb-2">Bot Type:</label>
            <select
              name="type"
              value={botType}
              onChange={handleBotTypeChange}
              className="w-full px-3 py-2 bg-gray-700 text-white border border-gray-600 rounded-md"
              disabled={isBotRunning}
            >
              <option value="grid">Grid Trading Bot</option>
              <option value="another">Another Strategy Bot</option>
            </select>
          </div>

          <div className="form-group">
            <label className="block text-gray-300 mb-2">API Key:</label>
            <input
              type="text"
              name="api_key"
              value={params.api_key}
              onChange={handleInputChange}
              className="w-full px-3 py-2 bg-gray-700 text-white border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
              disabled={isBotRunning}
            />
          </div>

          <div className="form-group">
            <label className="block text-gray-300 mb-2">API Secret:</label>
            <input
              type="password"
              name="api_secret"
              value={params.api_secret}
              onChange={handleInputChange}
              className="w-full px-3 py-2 bg-gray-700 text-white border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
              disabled={isBotRunning}
            />
          </div>

          <div className="form-group flex items-center space-x-2">
            <input
              type="checkbox"
              name="testnet"
              checked={params.testnet}
              onChange={handleInputChange}
              className="h-4 w-4 text-blue-600 bg-gray-700 border-gray-600 rounded"
              disabled={isBotRunning}
            />
            <label className="text-gray-300">Use Testnet</label>
          </div>

          {botType === 'grid' ? (
            <GridBotForm 
              params={params as GridTradingParameters}
              handleInputChange={handleInputChange}
              isBotRunning={isBotRunning}
            />
          ) : (
            <div className="col-span-2 text-gray-300">
              The form for another strategy will be available soon.
            </div>
          )}
        </div>

        <div className="button-group flex space-x-4 mt-4">
          {!isBotRunning ? (
            <button 
              type="submit" 
              className={`start-button px-4 py-2 rounded-md text-white font-semibold ${isLoading ? 'bg-green-400 cursor-not-allowed' : 'bg-green-600 hover:bg-green-700'}`}
              disabled={isLoading}
            >
              {isLoading ? 'Starting...' : 'Start Bot'}
            </button>
          ) : (
            <button 
              type="button" 
              onClick={handleStop} 
              className={`stop-button px-4 py-2 rounded-md text-white font-semibold ${isLoading ? 'bg-red-400 cursor-not-allowed' : 'bg-red-600 hover:bg-red-700'}`}
              disabled={isLoading}
            >
              {isLoading ? 'Stopping...' : 'Stop Bot'}
            </button>
          )}
        </div>
      </form>
    </div>
  );
};
