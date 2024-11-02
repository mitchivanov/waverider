import React, { useEffect, useRef, useState } from 'react';
import { createChart, IChartApi, ISeriesApi, LineData, ColorType, Time } from 'lightweight-charts';
import { botService } from '../services/api';
import { ActiveOrder, PriceData } from '../types';

interface ChartMarker {
  time: Time;
  position: 'aboveBar' | 'belowBar';
  color: string;
  shape: 'circle' | 'square' | 'arrowUp' | 'arrowDown';
  text: string;
}

export const PriceChart: React.FC = () => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const [priceData, setPriceData] = useState<LineData[]>([]);
  const [activeOrders, setActiveOrders] = useState<ActiveOrder[]>([]);

  useEffect(() => {
    if (chartContainerRef.current) {
      chartRef.current = createChart(chartContainerRef.current, {
        width: chartContainerRef.current.clientWidth,
        height: 800,
        timeScale: {
          timeVisible: true,
          secondsVisible: false,
          borderColor: '#D1D4DC',
          barSpacing: 15,
          minBarSpacing: 10,
          fixLeftEdge: false,
          fixRightEdge: false,
          lockVisibleTimeRangeOnResize: false,
          rightBarStaysOnScroll: true,
          borderVisible: true,
          visible: true,
          tickMarkFormatter: (time: number) => {
            const date = new Date(time * 1000);
            return date.toLocaleTimeString();
          },
        },
        rightPriceScale: {
          borderColor: '#D1D4DC',
          borderVisible: true,
          scaleMargins: {
            top: 0.1,
            bottom: 0.1,
          },
        },
        layout: {
          background: {
            type: 'solid' as ColorType,
            color: '#ffffff',
          },
          textColor: '#000',
        },
        grid: {
          horzLines: {
            color: '#F0F3FA',
          },
          vertLines: {
            color: '#F0F3FA',
          },
        },
        crosshair: {
          mode: 1,
          vertLine: {
            width: 1,
            color: '#2196F3',
            style: 2,
          },
          horzLine: {
            width: 1,
            color: '#2196F3',
            style: 2,
          },
        },
      });

      seriesRef.current = chartRef.current.addLineSeries({
        color: '#2196F3',
        lineWidth: 2,
        crosshairMarkerVisible: true,
        lastValueVisible: true,
        priceLineVisible: true,
      });

      const handleResize = () => {
        if (chartRef.current && chartContainerRef.current) {
          chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
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
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log('Received WebSocket data:', data);

      if (data.type === 'price_update') {
        const lineData: LineData = {
          time: new Date(data.timestamp).getTime() / 1000 as Time,
          value: data.price,
        };
        setPriceData((prevData) => [...prevData, lineData]);
        seriesRef.current?.update(lineData);
      }

      if (data.type === 'active_orders_data') {
        const orders: ActiveOrder[] = data.payload || [];
        setActiveOrders(orders);
        updateMarkers(orders);
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

  const updateMarkers = (orders: ActiveOrder[]) => {
    if (!seriesRef.current || !chartRef.current) return;

    const markers: ChartMarker[] = orders
      .map((order): ChartMarker => ({
        time: new Date(order.created_at || new Date()).getTime() / 1000 as Time,
        position: order.order_type === 'buy' ? 'belowBar' : 'aboveBar',
        color: order.order_type === 'buy' ? '#2196F3' : '#f44336',
        shape: order.order_type === 'buy' ? 'arrowUp' : 'arrowDown',
        text: `${order.order_type === 'buy' ? 'Buy @' : 'Sell @'} ${order.price}`,
      }))
      .sort((a, b) => (a.time as number) - (b.time as number));

    seriesRef.current.setMarkers(markers);
  };

  return (
    <div 
      ref={chartContainerRef} 
      style={{ 
        width: '100%', 
        height: '800px',
        margin: '20px 0 60px 0',
        padding: '0 20px'
      }} 
    />
  );
};
