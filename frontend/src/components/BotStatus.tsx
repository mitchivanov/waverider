import React, { useState } from 'react';
import useWebSocket from 'react-use-websocket';
import { botService } from '../services/api';
import { BotStatus as BotStatusType } from '../types';

export const BotStatus: React.FC = () => {
  const [status, setStatus] = useState<BotStatusType | null>(null);

  useWebSocket(botService.getWebSocketUrl(), {
    onMessage: (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'status_update') {
        setStatus(data.data);
      }
    },
    shouldReconnect: () => true,
    reconnectInterval: 3000,
  });

  if (!status) return <div>Загрузка...</div>;

  return (
    <div className="bot-status">
      <h2>Статус бота</h2>
      <div className="status-grid">
        <div className="status-item">
          <span className="label">Статус:</span>
          <span className={`value ${status.status}`}>
            {status.status === 'running' ? 'Работает' : 'Остановлен'}
          </span>
        </div>
        
        <div className="status-item">
          <span className="label">Текущая цена:</span>
          <span className="value">
            {status.current_price ? `$${status.current_price.toFixed(2)}` : 'Н/Д'}
          </span>
        </div>

        <div className="status-item">
          <span className="label">Отклонение:</span>
          <span className="value">
            {status.deviation ? `${status.deviation.toFixed(2)}%` : 'Н/Д'}
          </span>
          </div>

        {/* Realized profits */}
        <div className="status-item">
          <span className="label">Реализованная прибыль (A):</span>
          <span className={`value ${status.realized_profit_a >= 0 ? 'positive' : 'negative'}`}>
            {status.realized_profit_a.toFixed(8)}
          </span>
        </div>
        
        <div className="status-item">
          <span className="label">Реализованная прибыль (B):</span>
          <span className={`value ${status.realized_profit_b >= 0 ? 'positive' : 'negative'}`}>
            {status.realized_profit_b.toFixed(8)}
          </span>
        </div>

        <div className="status-item">
          <span className="label">Общая прибыль (USDT):</span>
          <span className={`value ${status.total_profit_usdt >= 0 ? 'positive' : 'negative'}`}>
            ${status.total_profit_usdt.toFixed(2)}
          </span>
        </div>

        {/* Unrealized profits */}
        <div className="status-item">
          <span className="label">Нереализованная прибыль (A):</span>
          <span className={`value ${status.unrealized_profit_a >= 0 ? 'positive' : 'negative'}`}>
            {status.unrealized_profit_a.toFixed(8)}
          </span>
        </div>
        
        <div className="status-item">
          <span className="label">Нереализованная прибыль (B):</span>
          <span className={`value ${status.unrealized_profit_b >= 0 ? 'positive' : 'negative'}`}>
            {status.unrealized_profit_b.toFixed(8)}
          </span>
        </div>

        <div className="status-item">
          <span className="label">Нереализованная прибыль (USDT):</span>
          <span className={`value ${status.unrealized_profit_usdt >= 0 ? 'positive' : 'negative'}`}>
            ${status.unrealized_profit_usdt.toFixed(2)}
          </span>
        </div>

        <div className="status-item">
          <span className="label">Number of Active Orders:</span>
          <span className="value">{status.active_orders_count}</span>
        </div>
        
        <div className="status-item">
          <span className="label">Number of Completed Trades:</span>
          <span className="value">{status.completed_trades_count}</span>
        </div>
        
        {status.running_time && (
          <div className="status-item">
            <span className="label">Strategy Duration:</span>
            <span className="value">{status.running_time}</span>
          </div>
        )}
      </div>
    </div>
  );
};
