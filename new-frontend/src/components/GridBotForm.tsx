import React, { useEffect, useState } from 'react';
import { GridTradingParameters } from '../types';
import { binanceService } from '../services/binanceService';
import { SearchableSelect } from './SearchableSelect';

interface GridBotFormProps {
  params: GridTradingParameters;
  handleInputChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => void;
  isBotRunning: boolean;
}

export const GridBotForm: React.FC<GridBotFormProps> = ({ params, handleInputChange, isBotRunning }) => {
  const [availableAssets, setAvailableAssets] = useState<{
    baseAssets: string[],
    quoteAssets: string[]
  }>({
    baseAssets: [],
    quoteAssets: []
  });

  useEffect(() => {
    const loadAssets = async () => {
      try {
        const exchangeInfo = await binanceService.getExchangeInfo();
        const assets = binanceService.parseExchangeInfo(exchangeInfo);
        setAvailableAssets(assets);
      } catch (error) {
        console.error('Error loading assets:', error);
      }
    };

    loadAssets();
  }, []);

  const handleSelectChange = (value: string, name: string) => {
    handleInputChange({
      target: { name, value }
    } as React.ChangeEvent<HTMLInputElement>);
  };

  return (
    <>
      <div className="form-group">
        <label className="block text-gray-300 mb-2">Base Asset:</label>
        <SearchableSelect
          options={availableAssets.baseAssets}
          value={(params as GridTradingParameters).baseAsset}
          onChange={handleSelectChange}
          name="baseAsset"
          placeholder="Choose base asset"
          disabled={isBotRunning}
        />
      </div>

      <div className="form-group">
        <label className="block text-gray-300 mb-2">Quote Asset:</label>
        <SearchableSelect
          options={availableAssets.quoteAssets}
          value={(params as GridTradingParameters).quoteAsset}
          onChange={handleSelectChange}
          name="quoteAsset"
          placeholder="Choose quote asset"
          disabled={isBotRunning}
        />
      </div>

      <div className="form-group">
        <label className="block text-gray-300 mb-2">Asset A Funds (USDT):</label>
        <input
          type="number"
          name="asset_a_funds"
          value={params.asset_a_funds}
          onChange={handleInputChange}
          className="w-full px-3 py-2 bg-gray-700 text-white border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          required
          min="0"
          step="0.01"
          disabled={isBotRunning}
        />
      </div>

      <div className="form-group">
        <label className="block text-gray-300 mb-2">Asset B Funds (BTC):</label>
        <input
          type="number"
          name="asset_b_funds"
          value={params.asset_b_funds}
          onChange={handleInputChange}
          className="w-full px-3 py-2 bg-gray-700 text-white border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          required
          min="0"
          step="0.00000001"
          disabled={isBotRunning}
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
          disabled={isBotRunning}
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
          disabled={isBotRunning}
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
          disabled={isBotRunning}
        />
      </div>

      <div className="form-group flex items-center space-x-2">
        <input
          type="checkbox"
          name="use_granular_distribution"
          checked={params.use_granular_distribution}
          onChange={handleInputChange}
          className="h-4 w-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
          disabled={isBotRunning}
        />
        <label className="text-gray-300">Use granular distribution</label>
      </div>

      <div className="form-group flex items-center space-x-2">
        <input
          type="checkbox"
          name="trail_price"
          checked={params.trail_price}
          onChange={handleInputChange}
          className="h-4 w-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
          disabled={isBotRunning}
        />
        <label className="text-gray-300">Trailing price</label>
      </div>

      <div className="form-group flex items-center space-x-2">
        <input
          type="checkbox"
          name="only_profitable_trades"
          checked={params.only_profitable_trades}
          onChange={handleInputChange}
          className="h-4 w-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
          disabled={isBotRunning}
        />
        <label className="text-gray-300">Only profitable trades</label>
      </div>
    </>
  );
};
