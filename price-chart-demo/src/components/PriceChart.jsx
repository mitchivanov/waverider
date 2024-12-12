import React, { useEffect, useRef } from 'react';
import {
  createChart,
  ColorType,
  LineStyle,
  CrosshairMode,
} from 'lightweight-charts';
import { generatePriceData, generateOrders } from '../utils/generateTestData';

export const PriceChart = () => {
  const chartContainerRef = useRef(null);
  const chartRef = useRef(null);
  const lineSeriesRef = useRef(null);
  const orderSeriesRefs = useRef([]);
  const tooltipRef = useRef(null);

  useEffect(() => {
    if (chartContainerRef.current) {
      const tooltip = document.createElement('div');
      tooltip.style.position = 'absolute';
      tooltip.style.display = 'none';
      tooltip.style.padding = '8px';
      tooltip.style.backgroundColor = 'rgba(30, 34, 45, 0.9)';
      tooltip.style.color = '#DDD';
      tooltip.style.borderRadius = '4px';
      tooltip.style.fontSize = '12px';
      tooltip.style.zIndex = '1000';
      chartContainerRef.current.appendChild(tooltip);
      tooltipRef.current = tooltip;

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
        crosshair: {
          mode: CrosshairMode.Normal,
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

      orders.forEach(order => {
        const orderSeries = chart.addLineSeries({
          color: order.type === 'buy' ? '#4CAF50' : '#FF5252',
          lineWidth: 1,
          lineStyle: LineStyle.Dotted,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });

        const markers = [
          {
            time: order.openTime,
            position: 'inBar',
            color: order.type === 'buy' ? '#4CAF50' : '#FF5252',
            shape: 'circle',
            text: `${order.type === 'buy' ? 'Buy' : 'Sell'} Open $${order.price}`,
          },
          {
            time: order.closeTime,
            position: 'inBar',
            color: order.type === 'buy' ? '#4CAF50' : '#FF5252',
            shape: 'circle',
            text: `${order.type === 'buy' ? 'Buy' : 'Sell'} Close $${order.price}`,
          }
        ];

        orderSeries.setData([
          { time: order.openTime, value: order.price },
          { time: order.closeTime, value: order.price }
        ]);
        
        orderSeries.setMarkers(markers);
        orderSeriesRefs.current.push({ series: orderSeries, orderInfo: order });
      });

      chart.timeScale().fitContent();

      return () => {
        chart.remove();
        tooltipRef.current?.remove();
      };
    }
  }, []);

  return (
    <div ref={chartContainerRef} style={{ position: 'relative' }} />
  );
};