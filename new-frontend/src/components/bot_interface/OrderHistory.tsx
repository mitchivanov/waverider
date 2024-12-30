import React, { useState, useEffect } from 'react';
import { useWebSocket } from '../../services/WebSocketMaster';
import { OrderHistory as OrderHistoryType } from '../../types';

interface OrderHistoryProps {
  botId: number;
}

export const OrderHistory: React.FC<OrderHistoryProps> = ({ botId }) => {
  const [orders, setOrders] = useState<OrderHistoryType[]>([]);
  const { lastMessage, subscribe, unsubscribe } = useWebSocket();

  useEffect(() => {
    subscribe(botId, 'order_history');
    return () => {
      unsubscribe(botId, 'order_history');
    };
  }, [botId, subscribe, unsubscribe]);

  useEffect(() => {
    const messageKey = `${botId}_order_history_data`;
    if (lastMessage[messageKey]) {
      setOrders(lastMessage[messageKey]);
    }
  }, [lastMessage, botId]);

  return (
    <div className="order-history bg-gray-800 p-6 rounded-lg shadow-lg">
      <h2 className="text-2xl font-semibold text-white mb-4">Order History</h2>
      <div className="overflow-auto max-h-[400px]">
        <table className="min-w-full bg-gray-700 rounded-md">
          <thead>
            <tr>
              <th className="py-2 px-4 bg-gray-600 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider">Order ID</th>
              <th className="py-2 px-4 bg-gray-600 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider">Type</th>
              <th className="py-2 px-4 bg-gray-600 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider">Price</th>
              <th className="py-2 px-4 bg-gray-600 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider">Quantity</th>
              <th className="py-2 px-4 bg-gray-600 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider">Status</th>
              <th className="py-2 px-4 bg-gray-600 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider">Created</th>
              <th className="py-2 px-4 bg-gray-600 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider">Updated</th>
            </tr>
          </thead>
          <tbody>
            {orders.length > 0 ? (
              orders.map((order) => (
                <tr key={order.order_id} className="text-gray-200">
                  <td className="py-2 px-4">{order.order_id}</td>
                  <td className="py-2 px-4">{order.order_type}</td>
                  <td className="py-2 px-4">${order.price.toFixed(2)}</td>
                  <td className="py-2 px-4">{order.quantity}</td>
                  <td className="py-2 px-4">{order.status}</td>
                  <td className="py-2 px-4">{new Date(order.created_at).toLocaleString()}</td>
                  <td className="py-2 px-4">{new Date(order.updated_at).toLocaleString()}</td>
                </tr>
              ))
            ) : (
              <tr className="text-gray-400">
                <td colSpan={7} className="py-2 px-4 text-center">No order history</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};