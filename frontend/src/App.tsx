import React from 'react';
import { BotControl } from './components/BotControl';
import { BotStatus } from './components/BotStatus';
import { TradeHistory } from './components/TradeHistory';
import { ActiveOrders } from './components/ActiveOrders';
import { PriceChart } from './components/PriceChart';
import { OrderHistory } from './components/OrderHistory';
import './App.css';

function App() {
  return (
    <div className="App">
      <h1>Trading Bot</h1>
      <div className="dashboard-grid">
        <BotControl />
        <BotStatus />
        <ActiveOrders />
        <OrderHistory />
        <TradeHistory />
        <PriceChart />
      </div>
    </div>
  );
}

export default App;
