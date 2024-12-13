import React from 'react';
import { toast } from 'react-hot-toast';

interface TradeNotificationProps {
  tradeType: string;
  buyPrice: number;
  sellPrice: number;
  quantity: number;
  symbol: string;
}

export const showTradeNotification = ({ tradeType, buyPrice, sellPrice, quantity, symbol }: TradeNotificationProps) => {
  const formattedBuyPrice = buyPrice.toFixed(2);
  const formattedSellPrice = sellPrice.toFixed(2);
  const formattedQuantity = quantity.toFixed(8);

  const message = (
    <div className="flex flex-col gap-1">
      <div className="font-semibold text-sm">
        New Trade: {tradeType === 'BUY_SELL' ? 'Long' : 'Short'}
      </div>
      <div className="text-xs">
        <div>Symbol: {symbol}</div>
        <div>Buy Price: ${formattedBuyPrice}</div>
        <div>Sell Price: ${formattedSellPrice}</div>
        <div>Quantity: {formattedQuantity}</div>
      </div>
    </div>
  );

  toast(message, {
    duration: 5000,
    position: 'top-right',
    className: 'bg-gray-800 text-white',
  });
};
