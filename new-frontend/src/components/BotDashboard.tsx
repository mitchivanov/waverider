import React, { useEffect } from 'react';
import { useWebSocket } from '../services/WebSocketMaster';
import { BotStatus } from './BotStatus';
import { TradeHistory } from './TradeHistory';
import { ActiveOrders } from './ActiveOrders';
import { OrderHistory } from './OrderHistory';
import { PriceChart } from './PriceChart';

interface BotDashboardProps {
    botId: number;
}

export const BotDashboard: React.FC<BotDashboardProps> = ({ botId }) => {
    const { subscribe, unsubscribe } = useWebSocket();

    useEffect(() => {
        // Подписываемся на все необходимые типы данных
        const subscriptions = [
            'status',
            'trade_history',
            'active_orders',
            'order_history',
            'price_data',
            'candlestick_data',
            'candlestick_1m'
        ];

        subscriptions.forEach(type => subscribe(botId, type));

        return () => {
            subscriptions.forEach(type => unsubscribe(botId, type));
        };
    }, [botId, subscribe, unsubscribe]);

    return (
        <div className="dashboard-grid grid grid-cols-1 lg:grid-cols-2 gap-6">
            <BotStatus botId={botId} />
            <ActiveOrders botId={botId} />
            <div className="flex flex-col">
                <PriceChart botId={botId} />
                <TradeHistory botId={botId} />
            </div>
            <OrderHistory botId={botId} />
        </div>
    );
};