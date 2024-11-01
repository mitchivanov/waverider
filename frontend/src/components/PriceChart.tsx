import React, { useState } from 'react';
import {
  Chart as ChartJS,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import 'chartjs-adapter-date-fns';
import { ru } from 'date-fns/locale';
import { ActiveOrder, BotStatus } from '../types';
import { botService } from '../services/api';
import useWebSocket from 'react-use-websocket';

ChartJS.register(
  TimeScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

interface PriceDataPoint {
  timestamp: string;
  price: number;
}

export const PriceChart: React.FC = () => {
  const [priceData, setPriceData] = useState<PriceDataPoint[]>([]);
  const [activeOrders, setActiveOrders] = useState<ActiveOrder[]>([]);
  const [status, setStatus] = useState<BotStatus | null>(null);

  useWebSocket(botService.getWebSocketUrl(), {
    onMessage: (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'price_update') {
        setPriceData((prev) => {
          const newData = [...prev, { timestamp: data.timestamp, price: data.price }];
          return newData.length > 100 ? newData.slice(-100) : newData;
        });
      }
      if (data.type === 'active_orders_data') {
        setActiveOrders(data.payload || []);
      }
      if (data.type === 'status_update') {
        setStatus(data.data);
      }
    },
    shouldReconnect: () => true,
    reconnectInterval: 3000,
  });

  if (!status || status.status !== 'active') {
    return (
      <div className="price-chart" style={{ height: '400px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span>График будет доступен после запуска стратегии</span>
      </div>
    );
  }

  const chartData = {
    labels: priceData.map(point => new Date(point.timestamp)),
    datasets: [
      {
        label: 'Цена',
        data: priceData.map(point => point.price),
        borderColor: 'rgb(75, 192, 192)',
        backgroundColor: 'rgba(75, 192, 192, 0.5)',
        tension: 0.1,
      }
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: {
        type: 'time' as const,
        time: {
          unit: 'minute' as const,
        },
        adapters: {
          date: {
            locale: ru,
          },
        },
      },
    },
  };

  return (
    <div className="price-chart" style={{ height: '400px' }}>
      <Line data={chartData} options={options} />
    </div>
  );
};