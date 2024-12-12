import React, { useEffect } from 'react';
import { SellBotParameters } from '../types';
import { SearchableSelect } from './SearchableSelect';

interface SellBotFormProps {
  params: SellBotParameters;
  handleInputChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => void;
  isBotRunning: boolean;
}

export const SellBotForm: React.FC<SellBotFormProps> = ({ params, handleInputChange, isBotRunning }) => {
  const handleSelectChange = (value: string, name: string) => {
    handleInputChange({
      target: { name, value }
    } as React.ChangeEvent<HTMLInputElement>);
  };

  useEffect(() => {
    if (params.baseAsset && params.quoteAsset) {
      handleInputChange({
        target: {
          name: 'symbol',
          value: `${params.baseAsset}${params.quoteAsset}`
        }
      } as React.ChangeEvent<HTMLInputElement>);
    }
  }, [params.baseAsset, params.quoteAsset]);

  return (
    <>
      <div className="form-group">
        <label className="block text-gray-300 mb-2">Base Asset:</label>
        <SearchableSelect
          options={['BTC', 'ETH', 'BNB']} // Можно расширить список
          value={params.baseAsset}
          onChange={handleSelectChange}
          name="baseAsset"
          placeholder="Choose base asset"
          disabled={isBotRunning}
          apiKey={params.api_key}
          apiSecret={params.api_secret}
        />
      </div>

      <div className="form-group">
        <label className="block text-gray-300 mb-2">Quote Asset:</label>
        <SearchableSelect
          options={['USDT', 'BUSD']} // Можно расширить список
          value={params.quoteAsset}
          onChange={handleSelectChange}
          name="quoteAsset"
          placeholder="Choose quote asset"
          disabled={isBotRunning}
          apiKey={params.api_key}
          apiSecret={params.api_secret}
        />
      </div>

      <div className="form-group">
        <label className="block text-gray-300 mb-2">Minimum Price:</label>
        <input
          type="number"
          name="min_price"
          value={params.min_price}
          onChange={handleInputChange}
          className="w-full px-3 py-2 bg-gray-700 text-white border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          required
          min="0"
          step="0.01"
          disabled={isBotRunning}
        />
      </div>

      <div className="form-group">
        <label className="block text-gray-300 mb-2">Maximum Price:</label>
        <input
          type="number"
          name="max_price"
          value={params.max_price}
          onChange={handleInputChange}
          className="w-full px-3 py-2 bg-gray-700 text-white border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          required
          min="0"
          step="0.01"
          disabled={isBotRunning}
        />
      </div>

      <div className="form-group">
        <label className="block text-gray-300 mb-2">Number of Levels:</label>
        <input
          type="number"
          name="num_levels"
          value={params.num_levels}
          onChange={handleInputChange}
          className="w-full px-3 py-2 bg-gray-700 text-white border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          required
          min="1"
          disabled={isBotRunning}
        />
      </div>

      <div className="form-group">
        <label className="block text-gray-300 mb-2">Reset Threshold (%):</label>
        <input
          type="number"
          name="reset_threshold_pct"
          value={params.reset_threshold_pct}
          onChange={handleInputChange}
          className="w-full px-3 py-2 bg-gray-700 text-white border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          required
          min="0"
          step="0.1"
          disabled={isBotRunning}
        />
      </div>

      <div className="form-group">
        <label className="block text-gray-300 mb-2">Batch Size:</label>
        <input
          type="number"
          name="batch_size"
          value={params.batch_size}
          onChange={handleInputChange}
          className="w-full px-3 py-2 bg-gray-700 text-white border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          required
          min="0.00000001"
          step="0.00000001"
          disabled={isBotRunning}
        />
      </div>
    </>
  );
};
