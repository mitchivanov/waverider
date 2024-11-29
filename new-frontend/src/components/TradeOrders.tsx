import React from 'react';
import { OrderHistory } from '../types';

interface TradeOrdersProps {
  orders: OrderHistory[];
}

export const TradeOrders: React.FC<TradeOrdersProps> = ({ orders }) => {
  return (
    <div className="trade-orders bg-gray-700 rounded-md">
      <table className="min-w-full bg-gray-600 rounded-md">
        <thead>
          <tr>
            <th className="py-2 px-4 bg-gray-500 text-left font-rubik text-sm font-semibold text-gray-200 uppercase tracking-wider">Order ID</th>
            <th className="py-2 px-4 bg-gray-500 text-left font-rubik text-sm font-semibold text-gray-200 uppercase tracking-wider">Type</th>
            <th className="py-2 px-4 bg-gray-500 text-left font-rubik text-sm font-semibold text-gray-200 uppercase tracking-wider">Price</th>
            <th className="py-2 px-4 bg-gray-500 text-left font-rubik text-sm font-semibold text-gray-200 uppercase tracking-wider">Quantity</th>
            <th className="py-2 px-4 bg-gray-500 text-left font-rubik text-sm font-semibold text-gray-200 uppercase tracking-wider">Status</th>
            <th className="py-2 px-4 bg-gray-500 text-left font-rubik text-sm font-semibold text-gray-200 uppercase tracking-wider">Created</th>
            <th className="py-2 px-4 bg-gray-500 text-left font-rubik text-sm font-semibold text-gray-200 uppercase tracking-wider">Updated</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((order) => (
            <tr key={order.order_id} className="text-gray-100">
              <td className="py-2 px-4">{order.order_id}</td>
              <td className="py-2 px-4">{order.order_type}</td>
              <td className="py-2 px-4">${order.price.toFixed(2)}</td>
              <td className="py-2 px-4">{order.quantity}</td>
              <td className="py-2 px-4">{order.status}</td>
              <td className="py-2 px-4">{new Date(order.created_at).toLocaleString()}</td>
              <td className="py-2 px-4">{new Date(order.updated_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};