import React, { createContext, useContext, useState, useCallback } from 'react';
import { toast } from 'react-hot-toast';
import { v4 as uuidv4 } from 'uuid';
import { Notification } from '../types';

interface NotificationContextType {
  notifications: Notification[];
  addNotification: (type: 'trade' | 'error' | 'info', message: string, details?: Record<string, any>) => void;
  clearNotifications: () => void;
}

const NotificationContext = createContext<NotificationContextType | null>(null);

export const NotificationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [notifications, setNotifications] = useState<Notification[]>([]);

  const addNotification = useCallback((type: 'trade' | 'error' | 'info', message: string, details?: Record<string, any>) => {
    const notification: Notification = {
      id: uuidv4(),
      type,
      message,
      details,
      timestamp: new Date()
    };

    setNotifications(prev => [notification, ...prev]);

    const toastMessage = (
      <div className="flex flex-col gap-1">
        <div className="font-semibold text-sm">{message}</div>
        {details && (
          <div className="text-xs">
            {Object.entries(details).map(([key, value]) => (
              <div key={key}>{key}: {value}</div>
            ))}
          </div>
        )}
      </div>
    );

    toast(toastMessage, {
      duration: 10000,
      position: 'top-right',
      className: `bg-gray-800 text-white ${type === 'error' ? 'border-l-4 border-red-500' : 
        type === 'trade' ? 'border-l-4 border-green-500' : 'border-l-4 border-blue-500'}`,
    });
  }, []);

  const clearNotifications = useCallback(() => {
    setNotifications([]);
  }, []);

  return (
    <NotificationContext.Provider value={{ notifications, addNotification, clearNotifications }}>
      {children}
    </NotificationContext.Provider>
  );
};

export const useNotifications = () => {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotifications must be used within a NotificationProvider');
  }
  return context;
};
