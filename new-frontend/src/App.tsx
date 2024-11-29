import React from 'react';
import { WebSocketProvider } from './services/WebSocketMaster';
import { BotControl } from './components/BotControl';
import { BotStatus } from './components/BotStatus';
import { TradeHistory } from './components/TradeHistory';
import { ActiveOrders } from './components/ActiveOrders';
import { OrderHistory } from './components/OrderHistory';
import { PriceChart } from './components/PriceChart';
import { Header } from './components/Header';
import './index.css';

function App() {
  return (
    <WebSocketProvider>
      <div className="App bg-almostGray min-h-screen pt-16 p-4">
        <Header />
        <h1 className="text-4xl font-bold text-center text-white mb-8">Trading Bot</h1>
        <div className="dashboard-grid grid grid-cols-1 lg:grid-cols-2 gap-6">
          <BotControl />
          <BotStatus />
          <ActiveOrders />
          <div className="flex flex-col">
            <PriceChart />
            <TradeHistory />
          </div>
        </div>
        <OrderHistory />
      </div>
    </WebSocketProvider>
  );
}

export default App;
