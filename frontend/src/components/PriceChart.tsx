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

const intervals = ['1m', '5m', '15m', '30m', '1h', '4h', '1d'];
const symbol = 'BTCUSDT'; // Или получайте динамически

export const PriceChart: React.FC = () => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const [activeOrders, setActiveOrders] = useState<ActiveOrder[]>([]);
  const [selectedInterval, setSelectedInterval] = useState<string>('1m');

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
    // Инициализация WebSocket подключения
    wsRef.current = new WebSocket("ws://localhost:8000/ws");

    wsRef.current.onopen = () => {
      console.log('WebSocket подключен');
      // Отправляем параметры подписки
      wsRef.current?.send(JSON.stringify({
        type: "subscribe",
        symbol: symbol,
        interval: selectedInterval
      }));
    };

    wsRef.current.onmessage = (event) => {
      const message = JSON.parse(event.data);
      const type = message.type;

      if (type === "historical_kline_data") {
        const historicalData: CandlestickData[] = message.data
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
        const orders = message.payload || [];
        setActiveOrders(orders);
        updateGridLevels(orders);
      }

      if (type === "kline_data" || type === "candlestick_update") {
        const kline: CandlestickData = {
          time: (type === "kline_data" ? message.data.open_time : message.data.time) / 1000 as Time,
          open: message.data.open,
          high: message.data.high,
          low: message.data.low,
          close: message.data.close,
        };
        
        try {
          candlestickSeriesRef.current?.update(kline);
        } catch (error) {
          console.warn('Ошибка при обновлении данных свечи:', error);
        }
      }
    };

    wsRef.current.onclose = () => {
      console.log('WebSocket отключен');
    };

    wsRef.current.onerror = (error) => {
      console.error('WebSocket ошибка:', error);
    };

    return () => {
      wsRef.current?.close();
    };
  }, [selectedInterval]);

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
    // Отправляем сообщение на сервер для изменения интервала
    wsRef.current?.send(JSON.stringify({
      type: "change_interval",
      interval: interval
    }));
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
