import React, { useState, useEffect } from 'react';
import { useWebSocket } from '../services/WebSocketMaster';
import { ActiveOrder } from '../types';

interface ActiveOrdersProps {
  botId: number;
}

export const ActiveOrders: React.FC<ActiveOrdersProps> = ({ botId }) => {
  const [orders, setOrders] = useState<ActiveOrder[]>([]);
  const { lastMessage, subscribe, unsubscribe } = useWebSocket();

  useEffect(() => {
    subscribe(botId, 'active_orders');
    return () => {
      unsubscribe(botId, 'active_orders');
    };
  }, [botId, subscribe, unsubscribe]);

  useEffect(() => {
    const key = `${botId}_active_orders_data`;
    if (lastMessage[key] && lastMessage[key].payload) {
      setOrders(lastMessage[key].payload);
    }
  }, [lastMessage, botId]);

  return (
    <div className="active-orders bg-gray-800 p-6 rounded-lg shadow-lg">
      <h2 className="text-2xl font-semibold text-white mb-4">Active Orders</h2>
      <div className="overflow-auto">
        <table className="min-w-full bg-gray-700 rounded-md">
          <thead>
            <tr>
              <th className="py-2 px-4 bg-gray-600 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider">ID</th>
              <th className="py-2 px-4 bg-gray-600 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider">Type</th>
              <th className="py-2 px-4 bg-gray-600 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider">Initial</th>
              <th className="py-2 px-4 bg-gray-600 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider">Price</th>
              <th className="py-2 px-4 bg-gray-600 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider">Quantity</th>
              <th className="py-2 px-4 bg-gray-600 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider">Created</th>
            </tr>
          </thead>
          <tbody>
            {orders.length > 0 ? (
              orders.map((order) => (
                <tr key={order.order_id} className="text-gray-200">
                  <td className="py-2 px-4">{order.order_id}</td>
                  <td className="py-2 px-4">{order.order_type}</td>
                  <td className="py-2 px-4">{order.isInitial ? 'Yes' : 'No'}</td>
                  <td className="py-2 px-4">${order.price.toFixed(2)}</td>
                  <td className="py-2 px-4">{order.quantity}</td>
                  <td className="py-2 px-4">{new Date(order.created_at).toLocaleString()}</td>
                </tr>
              ))
            ) : (
              <tr className="text-gray-400">
                <td colSpan={6} className="py-2 px-4 text-center">No active orders</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}; 