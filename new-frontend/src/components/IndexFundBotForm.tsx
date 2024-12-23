import React from 'react';
import { IndexFundParameters } from '../types';

interface IndexFundBotFormProps {
  params: IndexFundParameters;
  handleInputChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  isBotRunning: boolean;
}

export const IndexFundBotForm: React.FC<IndexFundBotFormProps> = ({
  params,
  handleInputChange,
  isBotRunning
}) => {
  return (
    <>
      <div className="form-group col-span-2 grid grid-cols-2 gap-4">
        <div>
          <label className="block text-gray-300 mb-2">Base Asset:</label>
          <input
            type="text"
            name="baseAsset"
            value={params.baseAsset}
            onChange={handleInputChange}
            className="w-full px-3 py-2 bg-gray-700 text-white border border-gray-600 rounded-md"
            disabled={isBotRunning}
          />
        </div>
        <div>
          <label className="block text-gray-300 mb-2">Quote Asset:</label>
          <input
            type="text"
            name="quoteAsset"
            value={params.quoteAsset}
            onChange={handleInputChange}
            className="w-full px-3 py-2 bg-gray-700 text-white border border-gray-600 rounded-md"
            disabled={isBotRunning}
          />
        </div>
      </div>

      <div className="form-group">
        <label className="block text-gray-300 mb-2">Asset A Funds:</label>
        <input
          type="number"
          name="asset_a_funds"
          value={params.asset_a_funds}
          onChange={handleInputChange}
          className="w-full px-3 py-2 bg-gray-700 text-white border border-gray-600 rounded-md"
          disabled={isBotRunning}
        />
      </div>

      <div className="form-group">
        <label className="block text-gray-300 mb-2">Asset B Funds:</label>
        <input
          type="number"
          name="asset_b_funds"
          value={params.asset_b_funds}
          onChange={handleInputChange}
          className="w-full px-3 py-2 bg-gray-700 text-white border border-gray-600 rounded-md"
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
          className="w-full px-3 py-2 bg-gray-700 text-white border border-gray-600 rounded-md"
          disabled={isBotRunning}
        />
      </div>

      <div className="form-group">
        <label className="block text-gray-300 mb-2">Deviation Threshold:</label>
        <input
          type="number"
          name="deviation_threshold"
          value={params.deviation_threshold}
          onChange={handleInputChange}
          className="w-full px-3 py-2 bg-gray-700 text-white border border-gray-600 rounded-md"
          disabled={isBotRunning}
        />
      </div>

      <div className="form-group">
        <label className="block text-gray-300 mb-2">Index Deviation Threshold:</label>
        <input
          type="number"
          name="index_deviation_threshold"
          value={params.index_deviation_threshold}
          onChange={handleInputChange}
          className="w-full px-3 py-2 bg-gray-700 text-white border border-gray-600 rounded-md"
          disabled={isBotRunning}
        />
      </div>

      <div className="form-group">
        <label className="block text-gray-300 mb-2">Growth Factor:</label>
        <input
          type="number"
          name="growth_factor"
          value={params.growth_factor}
          onChange={handleInputChange}
          className="w-full px-3 py-2 bg-gray-700 text-white border border-gray-600 rounded-md"
          disabled={isBotRunning}
        />
      </div>

      <div className="form-group flex items-center space-x-2">
        <input
          type="checkbox"
          name="use_granular_distribution"
          checked={params.use_granular_distribution}
          onChange={handleInputChange}
          className="h-4 w-4 text-blue-600 bg-gray-700 border-gray-600 rounded"
          disabled={isBotRunning}
        />
        <label className="text-gray-300">Use Granular Distribution</label>
      </div>

      <div className="form-group flex items-center space-x-2">
        <input
          type="checkbox"
          name="trail_price"
          checked={params.trail_price}
          onChange={handleInputChange}
          className="h-4 w-4 text-blue-600 bg-gray-700 border-gray-600 rounded"
          disabled={isBotRunning}
        />
        <label className="text-gray-300">Trail Price</label>
      </div>

      <div className="form-group flex items-center space-x-2">
        <input
          type="checkbox"
          name="only_profitable_trades"
          checked={params.only_profitable_trades}
          onChange={handleInputChange}
          className="h-4 w-4 text-blue-600 bg-gray-700 border-gray-600 rounded"
          disabled={isBotRunning}
        />
        <label className="text-gray-300">Only Profitable Trades</label>
      </div>
    </>
  );
};
