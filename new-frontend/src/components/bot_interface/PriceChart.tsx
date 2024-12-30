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
import { ActiveOrder, OrderHistory } from '../../types';

const intervals = ['1m', '5m', '15m', '30m', '1h', '4h', '1d'];

interface OrderLine {
  orderId: string;
  series: ISeriesApi<'Line'>;
}

export const PriceChart: React.FC<{ botId: number }> = ({ botId }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const [activeOrders, setActiveOrders] = useState<ActiveOrder[]>([]);
  const [selectedInterval, setSelectedInterval] = useState<string>('1m');

  // Ref для хранения ссылок на ценовые линии
  const priceLinesRef = useRef<OrderLine[]>([]);
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
        bot_id: botId,
        interval: selectedInterval
      }));
    };

    wsRef.current.onmessage = (event) => {
      const message = JSON.parse(event.data);
      const type = message.type;
      const bot_id = message.bot_id;

      if (type === "historical_kline_data" && bot_id === botId) {
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

      // Обрабатываем только новые свечи
      if ((type === "kline_data" || type === "candlestick_update") && bot_id === botId) {
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

      // Обрабатываем историю ордеров только один раз при получении
      if (type === "order_history_data" && bot_id === botId) {
        const orders = message.payload || [];
        const mappedOrders = orders.map((order: OrderHistory) => ({
          order_id: order.order_id,
          order_type: order.order_type as 'buy' | 'sell',
          isInitial: order.isInitial,
          price: order.price,
          quantity: order.quantity,
          created_at: order.created_at
        }));
        updateGridLevels(mappedOrders);
      }

      // Обрабатываем только изменения в активных ордерах
      if (type === "active_orders_data" && bot_id === botId) {
        const orders = message.payload || [];
        if (JSON.stringify(orders) !== JSON.stringify(activeOrders)) {
          setActiveOrders(orders);
          updateGridLevels(orders);
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
  }, [selectedInterval, botId]);

  const updateGridLevels = (orders: ActiveOrder[]) => {
    if (!candlestickSeriesRef.current || !chartRef.current) return;

    const existingOrderIds = new Set(priceLinesRef.current.map(line => line.orderId));
    const currentOrderIds = new Set(orders.map(order => order.order_id));

    // Проверяем, есть ли изменения
    let hasChanges = false;

    // Проверяем удаленные ордера
    priceLinesRef.current.forEach(line => {
      if (!currentOrderIds.has(line.orderId)) {
        chartRef.current?.removeSeries(line.series);
        hasChanges = true;
      }
    });

    // Обновляем массив только если были удаления
    if (hasChanges) {
      priceLinesRef.current = priceLinesRef.current.filter(line => 
        currentOrderIds.has(line.orderId)
      );
    }

    // Добавляем только новые ордера
    orders.forEach((order) => {
      if (!existingOrderIds.has(order.order_id)) {
        const orderSeries = chartRef.current?.addLineSeries({
          color: order.order_type === 'buy' ? '#4CAF50' : '#FF5252',
          lineWidth: 1,
          lineStyle: LineStyle.Dotted,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });

        if (orderSeries) {
          orderSeries.setData([
            { 
              time: (new Date(order.created_at).getTime() / 1000) - 3600 as Time,
              value: order.price 
            },
            { 
              time: new Date(order.created_at).getTime() / 1000 as Time,
              value: order.price 
            }
          ]);

          orderSeries.setMarkers([{
            time: new Date(order.created_at).getTime() / 1000 as Time,
            position: 'inBar',
            color: order.order_type === 'buy' ? '#4CAF50' : '#FF5252',
            shape: 'circle',
            text: `${order.order_type.toUpperCase()} ${order.isInitial ? '(Initial)' : ''} @ $${order.price.toFixed(2)}`,
          }]);

          priceLinesRef.current.push({
            orderId: order.order_id,
            series: orderSeries
          });
          hasChanges = true;
        }
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
