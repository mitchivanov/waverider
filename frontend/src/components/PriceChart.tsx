import React, { useEffect, useRef, useState } from 'react';
import {
  createChart,
  IChartApi,
  ISeriesApi,
  CandlestickData,
  ColorType,
  Time,
  IPriceLine,
  PriceLineOptions,
  LineStyle,
} from 'lightweight-charts';
import { botService } from '../services/api';
import { ActiveOrder } from '../types';

export const PriceChart: React.FC = () => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const [activeOrders, setActiveOrders] = useState<ActiveOrder[]>([]);

  // Ref для хранения ссылок на ценовые линии
  const priceLinesRef = useRef<IPriceLine[]>([]);

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
    const ws = new WebSocket(botService.getWebSocketUrl());

    ws.onopen = () => {
      console.log('WebSocket подключен к PriceChart');
      // При подключении отправляем подписку на ETHUSDT, если требуется
      ws.send(JSON.stringify({ type: 'subscribe', symbol: 'BTCUSDT' }));
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log('Получены данные по WebSocket:', data);

      if (data.type === 'candlestick_update' && data.symbol === 'BTCUSDT') {
        const candleData: CandlestickData = {
          time: data.data.time as Time,
          open: data.data.open,
          high: data.data.high,
          low: data.data.low,
          close: data.data.close,
        };
        candlestickSeriesRef.current?.update(candleData);
      }

      if (data.type === 'active_orders_data') {
        const orders: ActiveOrder[] = data.payload || [];
        setActiveOrders(orders);
        updateGridLevels(orders);
      }
    };

    ws.onclose = () => {
      console.log('WebSocket отключен от PriceChart');
    };

    ws.onerror = (error) => {
      console.error('WebSocket ошибка в PriceChart:', error);
    };

    return () => {
      ws.close();
    };
  }, []);

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

  return (
    <div className="price-chart-container" style={{ height: '500px' }}>
      <div
        ref={chartContainerRef}
        style={{
          width: '100%',
          height: '100%',
        }}
      />
    </div>
  );
};
