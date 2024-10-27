import React, { useEffect, useState } from 'react';
import axios from 'axios';

function ActiveOrders() {
    const [orders, setOrders] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [isBotRunning, setIsBotRunning] = useState(false);

    useEffect(() => {
        checkBotStatus();
        fetchOrders();
    }, []);

    const checkBotStatus = async () => {
        try {
            const response = await axios.get('/api/bot-status/');
            setIsBotRunning(response.data.is_running);
        } catch (error) {
            console.error('Error checking bot status:', error);
        }
    };

    const fetchOrders = async () => {
        try {
            setLoading(true);
            setError(null);
            const response = await axios.get('/api/active-orders/');
            console.log('Fetched orders:', response.data);
            setOrders(response.data);
        } catch (error) {
            console.error('Error fetching active orders:', error);
            if (error.response && error.response.data && error.response.data.error) {
                setError(error.response.data.error);
            } else {
                setError('Failed to fetch active orders. Please try again later.');
            }
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return <div>Loading active orders...</div>;
    }

    if (!isBotRunning) {
        return <div>The trading bot is not currently running.</div>;
    }

    if (error) {
        return <div>Error: {error}</div>;
    }

    return (
        <div>
            <h2>Active Orders</h2>
            {orders.length > 0 ? (
                <ul>
                    {orders.map(order => (
                        <li key={order.id}>
                            {order.order_type} {order.quantity} @ ${order.price}
                        </li>
                    ))}
                </ul>
            ) : (
                <p>No active orders at the moment.</p>
            )}
            <button onClick={fetchOrders}>Refresh Orders</button>
        </div>
    );
}

export default ActiveOrders;
