import React, { useEffect, useRef, useState } from 'react';
import { useWebSocket } from '../services/WebSocketMaster';
import { BotStatus } from './BotStatus';
import { TradeHistory } from './TradeHistory';
import { ActiveOrders } from './ActiveOrders';
import { OrderHistory } from './OrderHistory';
import { PriceChart } from './PriceChart';
import { useNotifications } from '../contexts/NotificationContext';

interface BotDashboardProps {
    botId: number;
}

export const BotDashboard: React.FC<BotDashboardProps> = ({ botId }) => {
    const { subscribe, unsubscribe, lastMessage } = useWebSocket();
    const { addNotification } = useNotifications();
    const lastProcessedNotification = useRef<string | null>(null);
    const [botType, setBotType] = useState<string | null>(null);

    useEffect(() => {
        // Получаем тип бота из статуса
        const statusKey = `${botId}_status`;
        if (lastMessage[statusKey]?.initial_parameters?.type) {
            setBotType(lastMessage[statusKey].initial_parameters.type);
        }
    }, [lastMessage, botId]);

    useEffect(() => {
        const subscriptions = [
            'status',
            'active_orders',
            'order_history',
            'price_data',
            'historical_kline_data',
            'kline_data',
            'candlestick_update',
            'candlestick_data',
            'candlestick_1m',
            'notification'
        ];

        // Добавляем подписку на trade_history только если это не sellbot
        if (botType !== 'sellbot') {
            subscriptions.push('trade_history');
        }

        subscriptions.forEach(type => subscribe(botId, type));

        return () => {
            subscriptions.forEach(type => unsubscribe(botId, type));
        };
    }, [botId, botType, subscribe, unsubscribe]);

    useEffect(() => {
        if (lastMessage[`${botId}_notification`]) {
            const notification = lastMessage[`${botId}_notification`];
            const notificationKey = `${notification.notification_type}_${notification.payload.buy_price}_${notification.payload.sell_price}`;
            
            if (lastProcessedNotification.current !== notificationKey) {
                lastProcessedNotification.current = notificationKey;
                
                if (notification.notification_type === 'new_trade') {
                    const { trade_type, buy_price, sell_price, quantity, symbol } = notification.payload;
                    addNotification('trade', 'New Trade Executed', {
                        type: trade_type === 'BUY_SELL' ? 'Long' : 'Short',
                        symbol: symbol,
                        buyPrice: `$${buy_price.toFixed(2)}`,
                        sellPrice: `$${sell_price.toFixed(2)}`,
                        quantity: quantity.toFixed(8)
                    });
                }
            }
        }
    }, [lastMessage, botId, addNotification]);

    return (
        <div className="dashboard-grid grid grid-cols-1 lg:grid-cols-2 gap-6">
            <BotStatus botId={botId} />
            <ActiveOrders botId={botId} />
            <div className="flex flex-col">
                <PriceChart botId={botId} />
                {botType !== 'sellbot' && <TradeHistory botId={botId} />}
            </div>
            <OrderHistory botId={botId} />
        </div>
    );
};