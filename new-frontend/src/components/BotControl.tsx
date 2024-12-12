import React, { useState, useEffect } from 'react';
import { botService } from '../services/api';
import { GridTradingParameters, AnotherTradingParameters, SellBotParameters } from '../types';
import { GridBotForm } from './GridBotForm';
import { SellBotForm } from './SellBotForm';
import { useWebSocket } from '../services/WebSocketMaster';

const defaultGridParams: GridTradingParameters = {
  type: 'grid',
  baseAsset: "BTC",
  quoteAsset: "USDT",
  asset_a_funds: 5000,
  asset_b_funds: 0.05,
  grids: 10,
  deviation_threshold: 0.004,
  growth_factor: 0.5,
  use_granular_distribution: true,
  trail_price: true,
  only_profitable_trades: false,
  api_key: '55euYhdLmx17qhTB1KhBSbrsS3A79bYU0C408VHMYsTTMcsyfSMboJ1d1uEWNLq3',
  api_secret: '2zlWvVVQIrj5ZryMNCkt9KIqowlQQMdG0bcV4g4LAinOnF8lc7O3Udumn6rIAyLb',
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

const defaultSellBotParams: SellBotParameters = {
  type: 'sellbot',
  baseAsset: "BTC",
  quoteAsset: "USDT",
  min_price: 90000,
  max_price: 110000,
  num_levels: 10,
  reset_threshold_pct: 2.0,
  batch_size: 0.001,
  api_key: '55euYhdLmx17qhTB1KhBSbrsS3A79bYU0C408VHMYsTTMcsyfSMboJ1d1uEWNLq3',
  api_secret: '2zlWvVVQIrj5ZryMNCkt9KIqowlQQMdG0bcV4g4LAinOnF8lc7O3Udumn6rIAyLb',
  testnet: true
};

interface BotControlProps {
  botId: number;
  onBotStarted: (newBotId: number) => void;
}

export const BotControl: React.FC<BotControlProps> = ({ botId, onBotStarted }) => {
  const [botType, setBotType] = useState<'grid' | 'sellbot'>('grid');
  const [params, setParams] = useState<GridTradingParameters | AnotherTradingParameters | SellBotParameters>(defaultGridParams);
  const [isLoading, setIsLoading] = useState(false);
  const [isBotRunning, setIsBotRunning] = useState(false);
  const { lastMessage, subscribe, unsubscribe } = useWebSocket();

  useEffect(() => {
    if (botId > 0) {
      subscribe(botId, 'bot_status');
      return () => {
        unsubscribe(botId, 'bot_status');
      };
    }
  }, [botId, subscribe, unsubscribe]);

  useEffect(() => {
    const key = `${botId}_bot_status`;
    if (lastMessage[key]) {
      setIsBotRunning(lastMessage[key].data.status === 'active');
    }
  }, [lastMessage, botId]);

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
    const newType = e.target.value as 'grid' | 'sellbot';
    setBotType(newType);
    setParams(newType === 'grid' ? defaultGridParams : defaultSellBotParams);
  };

  const handleStart = async () => {
    if (isLoading) return;
    try {
      setIsLoading(true);
      
      const baseAsset = botType === 'grid' 
        ? (params as GridTradingParameters).baseAsset 
        : (params as SellBotParameters).baseAsset;
        
      const quoteAsset = botType === 'grid' 
        ? (params as GridTradingParameters).quoteAsset 
        : (params as SellBotParameters).quoteAsset;

      const paramsToSend = {
        ...params,
        symbol: `${baseAsset}${quoteAsset}`
      };
      
      console.log('Sending params:', paramsToSend);
      
      const response = await botService.start(paramsToSend);
      alert('Bot started successfully');
      setIsBotRunning(true);
      onBotStarted(response.data.bot_id);
    } catch (error) {
      console.error('Error starting bot:', error);
      alert('Error starting the bot');
    } finally {
      setIsLoading(false);
    }
  };

  const handleStop = async () => {
    try {
      setIsLoading(true);
      await botService.stop(botId);
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
              <option value="sellbot">Sell Bot</option>
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
            <SellBotForm 
              params={params as SellBotParameters}
              handleInputChange={handleInputChange}
              isBotRunning={isBotRunning}
            />
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
