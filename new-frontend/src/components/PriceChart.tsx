import React, { useEffect, useRef, useState } from 'react';
import {
  createChart,
  IChartApi,
  ISeriesApi,
  CandlestickData,
  ColorType,
  IPriceLine,
  PriceLineOptions,
  LineStyle,
  Time,
} from 'lightweight-charts';
import { ActiveOrder } from '../types';
import { useWebSocket } from '../services/WebSocketMaster';

const intervals = ['1m', '5m', '15m', '30m', '1h', '4h', '1d'];
const symbol = 'BTCUSDT'; // Или получайте динамически

interface PriceChartProps {
  botId: number;
}

export const PriceChart: React.FC<PriceChartProps> = ({ botId }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const [activeOrders, setActiveOrders] = useState<ActiveOrder[]>([]);
  const [selectedInterval, setSelectedInterval] = useState<string>('1m');
  const { lastMessage, sendMessage } = useWebSocket();

  // Ref для хранения ссылок на ценовые линии
  const priceLinesRef = useRef<IPriceLine[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (chartContainerRef.current) {
      const container = chartContainerRef.current;
      chartRef.current = createChart(container, {
        width: container.clientWidth,
        height: container.clientHeight,
        timeScale: {
          timeVisible: true,
          secondsVisible: false,
        },
        rightPriceScale: {
          borderColor: '#D1D4DC',
        },
        layout: {
          background: {
            type: 'solid' as ColorType,
            color: '#0d1117',
          },
          textColor: '#c9d1d9',
        },
        grid: {
          horzLines: {
            color: '#30363d',
          },
          vertLines: {
            color: '#30363d',
          },
        },
        crosshair: {
          mode: 1,
        },
      });

      candlestickSeriesRef.current = chartRef.current.addCandlestickSeries({
        upColor: '#4caf50',
        downColor: '#f44336',
        borderDownColor: '#f44336',
        borderUpColor: '#4caf50',
        wickDownColor: '#f44336',
        wickUpColor: '#4caf50',
      });

      const handleResize = () => {
        if (chartRef.current && container) {
          chartRef.current.applyOptions({
            width: container.clientWidth,
            height: container.clientHeight,
          });
        }
      };

      window.addEventListener('resize', handleResize);

      return () => {
        window.removeEventListener('resize', handleResize);
        chartRef.current?.remove();
      };
    }
  }, []);

  useEffect(() => {
    const historicalKey = `${botId}_historical_kline_data`;
    const candleKey = `${botId}_kline_data`;
    const ordersKey = `${botId}_active_orders_data`;
    const candleUpdateKey = `${botId}_candlestick_update`;

    // Обработка исторических данных
    if (lastMessage[historicalKey]) {
      const historicalData: CandlestickData[] = lastMessage[historicalKey].data
        .map((k: any) => ({
          time: k.time as Time,
          open: k.open,
          high: k.high,
          low: k.low,
          close: k.close,
        }))
        .sort((a: CandlestickData, b: CandlestickData) => 
          Number(a.time) - Number(b.time)
        );
      
      candlestickSeriesRef.current?.setData(historicalData);
    }

    // Обработка обновлений свечей
    if (lastMessage[candleKey]) {
      const candleData = lastMessage[candleKey].data;
      const kline: CandlestickData = {
        time: candleData.time as Time,
        open: candleData.open,
        high: candleData.high,
        low: candleData.low,
        close: candleData.close,
      };
      candlestickSeriesRef.current?.update(kline);
    }

    // Обработка обновлений свечей реального времени
    if (lastMessage[candleUpdateKey]) {
      const candleData = lastMessage[candleUpdateKey].data;
      const kline: CandlestickData = {
        time: candleData.time as Time,
        open: candleData.open,
        high: candleData.high,
        low: candleData.low,
        close: candleData.close,
      };
      candlestickSeriesRef.current?.update(kline);
    }

    // Обработка активных ордеров
    if (lastMessage[ordersKey] && lastMessage[ordersKey].payload) {
      const orders = lastMessage[ordersKey].payload;
      setActiveOrders(orders);
      updateGridLevels(orders);
    }
  }, [lastMessage, botId]);

  const updateGridLevels = (orders: ActiveOrder[]) => {
    if (!candlestickSeriesRef.current) return;

    // Удаляем существующие ценовые линии
    priceLinesRef.current.forEach((line) => {
      candlestickSeriesRef.current?.removePriceLine(line);
    });
    // Очищаем массив ценовых линий
    priceLinesRef.current = [];

    // Добавляем новые уровни сетки на основе активных ордеров
    orders.forEach((order) => {
      const priceLineOptions: PriceLineOptions = {
        price: order.price,
        color: order.order_type === 'buy' ? '#4caf50' : '#f44336',
        lineWidth: 1,
        lineStyle: LineStyle.Dotted,
        axisLabelVisible: true,
        title: `${order.order_type === 'buy' ? 'BUY' : 'SELL'} @ ${order.price}`,
        lineVisible: true,
        axisLabelColor: '#ffffff',
        axisLabelTextColor: '#ffffff',
      };
      const priceLine = candlestickSeriesRef.current?.createPriceLine(priceLineOptions);
      if (priceLine) {
        priceLinesRef.current.push(priceLine);
      }
    });
  };

  const handleIntervalChange = (interval: string) => {
    setSelectedInterval(interval);
    // Используем общий WebSocket
    const message = {
      type: "change_interval",
      botId: botId, // Добавляем botId
      interval: interval,
      symbol: symbol
    };
    // Используем sendMessage из WebSocket контекста
    sendMessage(message);
  };
  return (
    <div>
      <div className="interval-buttons" style={{ marginBottom: '10px' }}>
        {intervals.map((interval) => (
          <button
            key={interval}
            onClick={() => handleIntervalChange(interval)}
            style={{
              marginRight: '5px',
              padding: '5px 10px',
              backgroundColor: selectedInterval === interval ? '#4caf50' : '#f44336',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
            }}
          >
            {interval}
          </button>
        ))}
      </div>
      <div className="price-chart-container" style={{ height: '500px' }}>
        <div
          ref={chartContainerRef}
          style={{
            width: '100%',
            height: '100%',
          }}
        />
      </div>
    </div>
  );
};