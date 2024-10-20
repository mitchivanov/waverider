import React, { useEffect, useState } from 'react';
import axios from 'axios';

function ActiveOrders() {
    const [orders, setOrders] = useState([]);

    useEffect(() => {
        // Fetch active orders from the backend API
        axios.get('/api/active-orders/')
            .then(response => {
                console.log('Fetched orders:', response.data);
                // Handle the response data
                setOrders(response.data); // Update state with the fetched orders
            })
            .catch(error => {
                console.error('Error fetching active orders:', error);
            });
    }, []); // Empty dependency array ensures this effect runs once on component mount

    return (
        <div>
            <h2>Active Orders</h2>
            <ul>
                {orders.map(order => (
                    <li key={order.id}>
                        {order.order_type} {order.quantity} @ ${order.price}
                    </li>
                ))}
            </ul>
        </div>
    );
}

export default ActiveOrders;
