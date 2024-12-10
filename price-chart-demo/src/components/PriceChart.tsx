import React, { useEffect, useRef } from 'react';
import {
  createChart,
  IChartApi,
  ISeriesApi,
  ColorType,
  LineStyle,
} from 'lightweight-charts';
import { generatePriceData, generateOrders } from '../utils/generateTestData';

export const PriceChart: React.FC = () => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const lineSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const orderSeriesRefs = useRef<ISeriesApi<'Line'>[]>([]);

  useEffect(() => {
    if (chartContainerRef.current) {
      const chart = createChart(chartContainerRef.current, {
        width: 800,
        height: 400,
        layout: {
          background: { type: ColorType.Solid, color: '#1E222D' },
          textColor: '#DDD'
        },
        grid: {
          vertLines: { color: '#2B2B43' },
          horzLines: { color: '#2B2B43' }
        },
        timeScale: {
          timeVisible: true,
          secondsVisible: false,
        },
      });

      chartRef.current = chart;
      
      const lineSeries = chart.addLineSeries({
        color: '#2962FF',
        lineWidth: 2,
        crosshairMarkerVisible: true,
        priceLineVisible: true,
        priceLineWidth: 1,
        priceLineColor: '#2962FF',
        priceLineStyle: LineStyle.Dotted,
      });
      
      lineSeriesRef.current = lineSeries;
      
      const priceData = generatePriceData(30);
      lineSeries.setData(priceData);
      
      const currentPrice = priceData[priceData.length - 1].value;
      const orders = generateOrders(currentPrice);

      // Создаем отдельную серию для каждого ордера
      orders.forEach(order => {
        const orderSeries = chart.addLineSeries({
          color: order.type === 'buy' ? '#4CAF50' : '#FF5252',
          lineWidth: 1,
          lineStyle: LineStyle.Dotted,
          priceLineVisible: false,
        });

        // Добавляем данные только для периода действия ордера
        orderSeries.setData([
          { time: order.openTime, value: order.price },
          { time: order.closeTime, value: order.price }
        ]);

        orderSeriesRefs.current.push(orderSeries);
      });

      chart.timeScale().fitContent();

      return () => {
        chart.remove();
      };
    }
  }, []);

  return (
    <div ref={chartContainerRef} />
  );
};