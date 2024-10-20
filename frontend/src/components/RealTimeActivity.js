import React, { useEffect, useState } from 'react';

const RealTimeActivity = () => {
    const [messages, setMessages] = useState([]);

    useEffect(() => {
        // Establish WebSocket connection
        const socket = new WebSocket('ws://localhost:8000/ws/django_bot/');

        // Handle connection open
        socket.onopen = () => {
            console.log('WebSocket connection opened');
        };

        // Handle incoming messages
        socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('WebSocket message received:', data);
            setMessages((prevMessages) => [...prevMessages, data]);
        };

        // Handle errors
        socket.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

        // Handle connection close
        socket.onclose = (event) => {
            console.log('WebSocket connection closed:', event);
        };

        // Cleanup on component unmount
        return () => {
            socket.close();
        };
    }, []);

    return (
        <div>
            <h2>Real-Time Activity</h2>
            <ul>
                {messages.map((message, index) => (
                    <li key={index}>{JSON.stringify(message)}</li>
                ))}
            </ul>
        </div>
    );
};

export default RealTimeActivity;

