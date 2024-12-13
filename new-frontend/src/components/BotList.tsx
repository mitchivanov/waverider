import React, { useState, useEffect, useRef, useCallback } from 'react';
import { botService } from '../services/api';
import { Bot } from '../types';

interface BotListProps {
  onBotSelect: (botId: number) => void;
  selectedBotId: number;
}

export const BotList: React.FC<BotListProps> = ({ onBotSelect, selectedBotId }) => {
  const [bots, setBots] = useState<Bot[]>([]);
  const intervalRef = useRef<NodeJS.Timeout>();
  const isMounted = useRef(true);

  const fetchBots = useCallback(async () => {
    if (!isMounted.current) return;
    
    try {
      const response = await botService.getBots();
      if (response.data.bots) {
        setBots(prevBots => {
          // Сравниваем новые данные со старыми
          const hasChanges = JSON.stringify(prevBots) !== JSON.stringify(response.data.bots);
          return hasChanges ? response.data.bots : prevBots;
        });
      }
    } catch (error) {
      console.error('Error fetching bots:', error);
    }
  }, []);

  useEffect(() => {
    console.log('BotList mounted');
    isMounted.current = true;
    fetchBots();
  
    intervalRef.current = setInterval(fetchBots, 10000);
    console.log('Set interval for fetchBots');
  
    return () => {
      console.log('BotList unmounted');
      isMounted.current = false;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        console.log('Cleared fetchBots interval');
      }
    };
  }, [fetchBots]);

  return (
    <div>
      <div className="bot-list bg-gray-800 p-4 rounded-lg mb-6">
        <h2 className="text-xl font-semibold text-white mb-4">Active Bots</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {bots.map((bot) => (
            <div
              key={bot.id}
              className={`cursor-pointer p-4 rounded-lg transition-colors ${
                selectedBotId === bot.id ? 'bg-blue-600' : 'bg-gray-700 hover:bg-gray-600'
              }`}
              onClick={() => onBotSelect(bot.id)}
            >
              <div className="text-white font-medium">{bot.symbol}</div>
              <div className="text-sm text-gray-300">Type: {bot.type}</div>
              <div className="text-sm text-gray-300">
                Status: <span className={bot.status === 'active' ? 'text-green-400' : 'text-red-400'}>
                  {bot.status}
                </span>
              </div>
            </div>
          ))}
          
          <div
            className="cursor-pointer p-4 rounded-lg bg-gray-700 hover:bg-gray-600 flex flex-col items-center justify-center min-h-[120px]"
            onClick={() => onBotSelect(-1)}
          >
            <div className="text-4xl text-gray-400 mb-2">+</div>
            <div className="text-sm text-gray-400">Create New Bot</div>
          </div>
        </div>
      </div>
    </div>
  );
};
