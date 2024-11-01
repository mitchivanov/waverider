import React from 'react';
import { BotControl } from './components/BotControl';
import { BotStatus } from './components/BotStatus';
import { TradeHistory } from './components/TradeHistory';
import { ActiveOrders } from './components/ActiveOrders';
import { botService } from './services/api';
import { PriceChart } from './components/PriceChart';
import './App.css';

function App() {
  return (
    <div className="App">
      <h1>Trading Bot</h1>
      <div className="dashboard-grid">
        <BotControl />
        <BotStatus />
        <PriceChart />
        <ActiveOrders />
        <TradeHistory />
      </div>
    </div>
  );
}

export default App;
