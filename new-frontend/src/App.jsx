import React from 'react';
import { BotControl } from './components/BotControl';

import './App.css'

function App() {
  return (
    <div className="App">
      <h1>Trading Bot</h1>
      <div className="dashboard-grid">
        <BotControl />
        {/* Другие компоненты */}
      </div>
    </div>
  );
}

export default App;
