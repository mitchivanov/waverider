import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { botService } from '../services/api';

interface WebSocketContextType {
  lastMessage: any;
  sendMessage: (message: any) => void;
  connected: boolean;
  subscribe: (message: any) => void;
}

const WebSocketContext = createContext<WebSocketContextType | null>(null);

const RECONNECT_INTERVAL = 3000;
const MAX_RETRIES = 5;

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [socket, setSocket] = useState<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<any>(null);
  const reconnectCount = useRef(0);
  const reconnectTimeout = useRef<NodeJS.Timeout>();
  const pendingMessages = useRef<any[]>([]);
  const subscriptions = useRef<any[]>([]);

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(botService.getWebSocketUrl());

      ws.onopen = () => {
        console.log('WebSocket connected');
        setConnected(true);
        reconnectCount.current = 0;
        
        // Отправляем накопившиеся сообщения
        while (pendingMessages.current.length > 0) {
          const message = pendingMessages.current.shift();
          if (message) ws.send(JSON.stringify(message));
        }

        // Отправляем подписочные сообщения
        subscriptions.current.forEach(message => {
          ws.send(JSON.stringify(message));
        });
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setLastMessage(data);
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

  const subscribe = useCallback((message: any) => {
    subscriptions.current.push(message);
    sendMessage(message);
  }, [sendMessage]);

  return (
    <WebSocketContext.Provider value={{ lastMessage, sendMessage, connected, subscribe }}>
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