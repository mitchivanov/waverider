import React, { useState, useCallback } from 'react';
import { WebSocketProvider } from './services/WebSocketMaster';
import { BotList } from './components/BotList';
import { BotControl } from './components/BotControl';
import { Header } from './components/Header';
import { BotDashboard } from './components/BotDashboard';
import './index.css';

function App() {
  const [selectedBotId, setSelectedBotId] = useState<number>(-1);
  const [isCreatingNewBot, setIsCreatingNewBot] = useState(false);

  const handleBotStarted = useCallback((newBotId: number) => {
    setSelectedBotId(newBotId);
    setIsCreatingNewBot(false);
  }, []);

  const handleBotSelect = useCallback((id: number) => {
    if (id === -1) {
      setIsCreatingNewBot(true);
      setSelectedBotId(-1);
    } else {
      setSelectedBotId(id);
      setIsCreatingNewBot(false);
    }
  }, []);

  return (
    <WebSocketProvider>
      <div className="App bg-almostGray min-h-screen pt-16 p-4">
        <Header/>
        <h1 className="text-4xl font-bold text-center text-white mb-8">Trading Bot</h1>
        <BotList 
          onBotSelect={handleBotSelect}
          selectedBotId={selectedBotId} 
        />
        
        {isCreatingNewBot ? (
          <div className="dashboard-grid">
            <BotControl botId={-1} onBotStarted={handleBotStarted} />
          </div>
        ) : selectedBotId > 0 && (
          <BotDashboard botId={selectedBotId} />
        )}
      </div>
    </WebSocketProvider>
  );
}

export default App;
