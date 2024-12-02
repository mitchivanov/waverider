import React, { useState, useEffect } from 'react';
import { useWebSocket } from '../services/WebSocketMaster';
import { TradeHistory as TradeHistoryType, OrderHistory } from '../types';
import { TradeOrders } from './TradeOrders';

interface TradeHistoryProps {
  botId: number;
}

export const TradeHistory: React.FC<TradeHistoryProps> = ({ botId }) => {
  const [trades, setTrades] = useState<TradeHistoryType[]>([]);
  const [orderHistory, setOrderHistory] = useState<OrderHistory[]>([]);
  const [expandedTradeId, setExpandedTradeId] = useState<string | null>(null);
  const { lastMessage } = useWebSocket();

  useEffect(() => {
    const tradeKey = `${botId}_trade_history_data`;
    const orderKey = `${botId}_order_history_data`;
    
    if (lastMessage[tradeKey] && lastMessage[tradeKey].payload) {
      setTrades(lastMessage[tradeKey].payload);
    }
    if (lastMessage[orderKey] && lastMessage[orderKey].payload) {
      setOrderHistory(lastMessage[orderKey].payload);
    }
  }, [lastMessage, botId]);

  const handleRowClick = (trade: TradeHistoryType) => {
    setExpandedTradeId(expandedTradeId === trade.buy_order_id ? null : trade.buy_order_id);
  };

  return (
    <div className="trade-history bg-gray-800 p-6 rounded-lg shadow-lg">
      <h2 className="text-2xl font-semibold text-white mb-4">Trade History</h2>
      <div className="overflow-auto">
        <table className="min-w-full bg-gray-700 rounded-md">
          <thead>
            <tr>
              {[
                { key: 'buy_price', label: 'Buy Price' },
                { key: 'sell_price', label: 'Sell Price' },
                { key: 'quantity', label: 'Quantity' },
                { key: 'profit', label: 'Profit' },
                { key: 'profit_asset', label: 'Profit Asset' },
                { key: 'status', label: 'Status' },
                { key: 'trade_type', label: 'Trade Type' },
                { key: 'executed_at', label: 'Execution Date' }
              ].map(({ key, label }) => (
                <th 
                  key={key}
                  className="py-2 px-4 bg-gray-600 text-left font-rubik text-xs font-semibold text-gray-300 uppercase tracking-wider cursor-pointer hover:bg-gray-500"
                >
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {trades.length > 0 ? (
              trades.map((trade) => {
                const relatedOrders = orderHistory.filter(
                  (order: OrderHistory) =>
                    order.order_id === trade.buy_order_id ||
                    order.order_id === trade.sell_order_id
                );

                return (
                  <React.Fragment key={trade.buy_order_id}>
                    <tr
                      className="text-gray-200 font-rubik font-normal cursor-pointer"
                      onClick={() => handleRowClick(trade)}
                    >
                      <td className="py-2 px-4">${trade.buy_price}</td>
                      <td className="py-2 px-4">${trade.sell_price}</td>
                      <td className="py-2 px-4">{trade.quantity}</td>
                      <td className={`py-2 px-4 ${trade.profit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        ${trade.profit.toFixed(2)}
                      </td>
                      <td className="py-2 px-4">{trade.profit_asset}</td>
                      <td className="py-2 px-4">{trade.status}</td>
                      <td className="py-2 px-4">{trade.trade_type === 'SELL_BUY' ? 'Short' : 'Long'}</td>
                      <td className="py-2 px-4">{trade.executed_at ? new Date(trade.executed_at).toLocaleString() : 'N/A'}</td>
                    </tr>
                    {expandedTradeId === trade.buy_order_id && relatedOrders.length > 0 && (
                      <tr>
                        <td colSpan={10}>
                          <TradeOrders orders={relatedOrders} />
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })
            ) : (
              <tr className="text-gray-400">
                <td colSpan={10} className="py-2 px-4 text-center">No trade history</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};