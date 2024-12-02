import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { botService } from '../services/api';

interface WebSocketContextType {
  lastMessage: Record<string, any>;
  sendMessage: (message: any) => void;
  connected: boolean;
  subscribe: (botId: number, type: string) => void;
  unsubscribe: (botId: number, type: string) => void;
}

const WebSocketContext = createContext<WebSocketContextType | null>(null);

const RECONNECT_INTERVAL = 3000;
const MAX_RETRIES = 5;

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [socket, setSocket] = useState<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<Record<string, any>>({});
  const reconnectCount = useRef(0);
  const reconnectTimeout = useRef<NodeJS.Timeout>();
  const pendingMessages = useRef<any[]>([]);
  const subscriptions = useRef<Map<number, Set<string>>>(new Map());

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(botService.getWebSocketUrl());

      ws.onopen = () => {
        console.log('WebSocket connected');
        setConnected(true);
        reconnectCount.current = 0;
        
        // Восстанавливаем все подписки
        subscriptions.current.forEach((types, botId) => {
          types.forEach(type => {
            ws.send(JSON.stringify({
              action: 'subscribe',
              bot_id: botId,
              type: type
            }));
          });
        });
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          const { bot_id, type } = data;
          
          if (bot_id && type) {
            const messageKey = `${bot_id}_${type}`;
            setLastMessage(prev => ({
              ...prev,
              [messageKey]: data
            }));
          } else {
            // Обработка сообщений без bot_id
            setLastMessage(prev => ({
              ...prev,
              global: data
            }));
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setConnected(false);
        
        // Пытаемся переподключиться с увеличивающейся задержкой
        if (reconnectCount.current < MAX_RETRIES) {
          const timeout = RECONNECT_INTERVAL * Math.pow(2, reconnectCount.current);
          console.log(`Attempting to reconnect in ${timeout}ms...`);
          reconnectTimeout.current = setTimeout(() => {
            reconnectCount.current += 1;
            connect();
          }, timeout);
        } else {
          console.error('Max reconnection attempts reached');
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };

      setSocket(ws);
    } catch (error) {
      console.error('Error creating WebSocket connection:', error);
    }
  }, []);

  useEffect(() => {
    connect();

    return () => {
      if (socket) {
        socket.close();
      }
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current);
      }
    };
  }, [connect]);

  const sendMessage = useCallback((message: any) => {
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(message));
    } else {
      // Сохраняем сообщение для отправки после переподключения
      pendingMessages.current.push(message);
    }
  }, [socket]);

  const subscribe = useCallback((botId: number, type: string) => {
    if (!subscriptions.current.has(botId)) {
      subscriptions.current.set(botId, new Set());
    }
    subscriptions.current.get(botId)?.add(type);
    
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({
        action: 'subscribe',
        bot_id: botId,
        type: type
      }));
    }
  }, [socket]);

  const unsubscribe = useCallback((botId: number, type: string) => {
    if (subscriptions.current.has(botId)) {
      subscriptions.current.get(botId)?.delete(type);
    }
  }, []);

  return (
    <WebSocketContext.Provider value={{ lastMessage, sendMessage, connected, subscribe, unsubscribe }}>
      {children}
    </WebSocketContext.Provider>
  );
};

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  return context;
};