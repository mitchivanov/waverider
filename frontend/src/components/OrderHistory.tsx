import React, { useState } from 'react';
import useWebSocket from 'react-use-websocket';
import { OrderHistory as OrderHistoryType } from '../types';
import { botService } from '../services/api';

export const OrderHistory: React.FC = () => {
  const [orders, setOrders] = useState<OrderHistoryType[]>([]);

  useWebSocket(botService.getWebSocketUrl(), {
    onMessage: (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'order_history_data') {
        setOrders(data.payload || []);
      }
    },
    shouldReconnect: () => true,
    reconnectInterval: 3000,
  });

  return (
    <div className="order-history">
      <h2>Order History</h2>
      <table>
        <thead>
          <tr>
            <th>Order ID</th>
            <th>Type</th>
            <th>Price</th>
            <th>Quantity</th>
            <th>Status</th>
            <th>Created</th>
            <th>Updated</th>
          </tr>
        </thead>
        <tbody>
          {orders.length > 0 ? (
            orders.map((order) => (
              <tr key={order.order_id}>
                <td>{order.order_id}</td>
                <td>{order.order_type}</td>
                <td>${order.price.toFixed(2)}</td>
                <td>{order.quantity}</td>
                <td>{order.status}</td>
                <td>{new Date(order.created_at).toLocaleString()}</td>
                <td>{new Date(order.updated_at).toLocaleString()}</td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan={7}>No order history</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
};
