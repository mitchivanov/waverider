const express = require('express');
const axios = require('axios');
const app = express();

// Define the port number for your Node.js backend
const PORT = 3000;

// Middleware to parse JSON requests
app.use(express.json());

// Route for checking bot status
app.get('/api/bot-status/', async (req, res) => {
  try {
    const response = await axios.get('http://localhost:8000/api/bot-status/');
    res.json(response.data);
  } catch (error) {
    console.error('Error fetching bot status:', error.message);
    res.status(500).json({ error: 'Failed to fetch bot status' });
  }
});

// Route for fetching active orders
app.get('/api/active-orders/', async (req, res) => {
  try {
    const response = await axios.get('http://localhost:8000/api/active-orders/');
    const activeOrders = response.data;
    res.json(activeOrders);
  } catch (error) {
    console.error('Error fetching active orders:', error.message);
    res.status(500).json({ error: 'Failed to fetch active orders' });
  }
});

// Start the server
app.listen(PORT, () => {
    console.log(`Server running at http://localhost:${PORT}/`);
});

// Function to simulate fetching active orders from your strategy
function getActiveOrdersFromStrategy() {
    // Replace with your actual implementation
    return [
        { id: 1, order_type: 'buy', quantity: 10, price: 100 },
        { id: 2, order_type: 'sell', quantity: 5, price: 150 },
    ];
}
