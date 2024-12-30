import React, { useState, useEffect } from 'react';
import { useWebSocket } from '../../services/WebSocketMaster';
import { BotStatus as BotStatusType } from '../../types';

interface BotStatusProps {
  botId: number;
}

export const BotStatus: React.FC<BotStatusProps> = ({ botId }) => {
  const [status, setStatus] = useState<BotStatusType | null>(null);
  const { lastMessage } = useWebSocket();

  useEffect(() => {
    const messageKey = `${botId}_bot_status_data`;
    console.debug('BotStatus lastMessage:', lastMessage);
    console.debug('BotStatus messageKey:', messageKey);
    if (lastMessage[messageKey]) {
      console.debug('BotStatus setting status:', lastMessage[messageKey]);
      setStatus(lastMessage[messageKey]);
    }
  }, [lastMessage, botId]);

  if (!status) return <div className="text-gray-300">Loading...</div>;

  return (
    <div className="bot-status bg-gray-800 p-6 rounded-lg shadow-lg">
      <h2 className="text-2xl font-semibold text-white mb-4">Bot Status</h2>
      <div className="status-grid grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <div className="status-item bg-gray-700 p-4 rounded-md">
          <span className="label block text-gray-400">Status:</span>
          <span className={`value ${status.status === 'active' ? 'text-green-400' : 'text-red-400'}`}>
            {status.status === 'active' ? 'Active' : 'Stopped'}
          </span>
        </div>

        <div className="status-item bg-gray-700 p-4 rounded-md">
          <span className="label block text-gray-400">Current Price:</span>
          <span className="value text-white">
            {status.current_price ? `$${status.current_price}` : 'N/A'}
          </span>
        </div>

        <div className="status-item bg-gray-700 p-4 rounded-md">
          <span className="label block text-gray-400">Deviation:</span>
          <span className="value text-white">
            {status.deviation ? `${status.deviation}%` : 'N/A'}
          </span>
        </div>

        {status.running_time && (
          <div className="status-item bg-gray-700 p-4 rounded-md">
            <span className="label block text-gray-400">Strategy Duration:</span>
            <span className="value text-white">{status.running_time}</span>
          </div>
        )}

        <div className="status-item bg-gray-700 p-4 rounded-md">
          <span className="label block text-gray-400">Number of Active Orders:</span>
          <span className="value text-white">{status.active_orders_count}</span>
        </div>

        <div className="status-item bg-gray-700 p-4 rounded-md">
          <span className="label block text-gray-400">Number of Completed Trades:</span>
          <span className="value text-white">{status.completed_trades_count}</span>
        </div>

        <div className="status-item bg-gray-700 p-4 rounded-md">
          <span className="label block text-gray-400">Realized Profit (A):</span>
          <span className={`value ${status.realized_profit_a >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {status.realized_profit_a.toFixed(8)}
          </span>
        </div>

        <div className="status-item bg-gray-700 p-4 rounded-md">
          <span className="label block text-gray-400">Unrealized Profit (A):</span>
          <span className={`value ${status.unrealized_profit_a >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {status.unrealized_profit_a.toFixed(8)}
          </span>
        </div>

        <div className="status-item bg-gray-700 p-4 rounded-md">
          <span className="label block text-gray-400">Realized Profit (B):</span>
          <span className={`value ${status.realized_profit_b >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {status.realized_profit_b.toFixed(8)}
          </span>
        </div>

        <div className="status-item bg-gray-700 p-4 rounded-md">
          <span className="label block text-gray-400">Unrealized Profit (B):</span>
          <span className={`value ${status.unrealized_profit_b >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {status.unrealized_profit_b.toFixed(8)}
          </span>
        </div>

        <div className="status-item bg-gray-700 p-4 rounded-md">
          <span className="label block text-gray-400">Total Profit (USDT):</span>
          <span className={`value ${status.total_profit_usdt >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            ${status.total_profit_usdt.toFixed(2)}
          </span>
        </div>
      </div>
    </div>
  );
};
