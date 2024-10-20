import React from 'react';
import TradingParametersForm from './components/TradingParametersForm';
import RealTimeActivity from './components/RealTimeActivity';
import ActiveOrders from './components/ActiveOrders';

function App() {
  return (
    <div className="App">
      <h1>Trading Bot Dashboard</h1>
      <TradingParametersForm />
      <RealTimeActivity />
      <ActiveOrders />
      {/* Include TradeHistory component */}
    </div>
  );
}

export default App;
