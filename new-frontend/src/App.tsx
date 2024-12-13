import React, { useState, useCallback } from 'react';
import { WebSocketProvider } from './services/WebSocketMaster';
import { BotList } from './components/BotList';
import { BotControl } from './components/BotControl';
import { Header } from './components/Header';
import { BotDashboard } from './components/BotDashboard';
import { LoginForm } from './components/LoginForm';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import './index.css';
import { Toaster } from 'react-hot-toast';
import { NotificationProvider } from './contexts/NotificationContext';

const AppContent: React.FC = () => {
  const { isAuthenticated } = useAuth();
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

  if (!isAuthenticated) {
    return <LoginForm />;
  }

  return (
    <WebSocketProvider>
      <NotificationProvider>
        <Toaster
          position="top-right"
          toastOptions={{
            duration: 10000,
            className: 'bg-gray-800 text-white',
          }}
        />
        <div className="App bg-almostGray min-h-screen pt-16 p-4">
          <Header />
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
      </NotificationProvider>
    </WebSocketProvider>
  );
};

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;
