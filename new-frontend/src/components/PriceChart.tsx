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
const symbol = 'BTCUSDT';

export const PriceChart: React.FC = () => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const [activeOrders, setActiveOrders] = useState<ActiveOrder[]>([]);
  const [selectedInterval, setSelectedInterval] = useState<string>('1m');
  const priceLinesRef = useRef<IPriceLine[]>([]);
  
  const { subscribe, lastMessage } = useWebSocket();

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

  // Подписка на данные при монтировании и смене интервала
  useEffect(() => {
    subscribe({
      type: "subscribe",
      symbol: symbol,
      interval: selectedInterval
    });
  }, [symbol, selectedInterval, subscribe]);

  // Обработка входящих сообщений
  useEffect(() => {
    if (!lastMessage) return;

    const { type, data, payload } = lastMessage;

    if (type === "historical_kline_data") {
      const historicalData: CandlestickData[] = data
        .map((k: any) => ({
          time: k.open_time / 1000,
          open: k.open,
          high: k.high,
          low: k.low,
          close: k.close,
        }))
        .sort((a: CandlestickData, b: CandlestickData) => 
          Number(a.time) - Number(b.time)
        )
        .slice(-100);
      
      candlestickSeriesRef.current?.setData(historicalData);
    }

    if (type === "active_orders_data") {
      const orders = payload || [];
      setActiveOrders(orders);
      updateGridLevels(orders);
    }

    if (type === "kline_data" || type === "candlestick_update") {
      const kline: CandlestickData = {
        time: (type === "kline_data" ? data.open_time : data.time) / 1000 as Time,
        open: data.open,
        high: data.high,
        low: data.low,
        close: data.close,
      };
      
      try {
        candlestickSeriesRef.current?.update(kline);
      } catch (error) {
        console.warn('Ошибка при обновлении данных свечи:', error);
      }
    }
  }, [lastMessage]);

  const updateGridLevels = (orders: ActiveOrder[]) => {
    if (!candlestickSeriesRef.current) return;

    // Remove existing price lines
    priceLinesRef.current.forEach((line) => {
      candlestickSeriesRef.current?.removePriceLine(line);
    });
    // Clear the array
    priceLinesRef.current = [];

    // Add new price lines based on active orders
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
    subscribe({
      type: "change_interval",
      interval: interval
    });
  };

  return (
    <div className="price-chart-container w-full bg-gray-800 p-6 rounded-lg shadow-lg">
      <div className="mb-4">
        <div className="interval-buttons flex flex-wrap gap-2">
          {intervals.map((interval) => (
            <button
              key={interval}
              onClick={() => handleIntervalChange(interval)}
              className={`px-3 py-1 rounded-md text-white ${selectedInterval === interval ? 'bg-green-500' : 'bg-red-500 hover:bg-red-600'}`}
            >
              {interval}
            </button>
          ))}
        </div>
      </div>
      <div className="price-chart-area h-96">
        <div
          ref={chartContainerRef}
          className="w-full h-full"
        />
      </div>
    </div>
  );
};