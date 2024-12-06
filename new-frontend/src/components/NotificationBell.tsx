import React, { useState } from 'react';
import { BsBell, BsBellFill } from 'react-icons/bs';
import { Notification } from '../types';

interface NotificationBellProps {
  notifications: Notification[];
}

export const NotificationBell: React.FC<NotificationBellProps> = ({ notifications }) => {
  const [isOpen, setIsOpen] = useState(false);

  const getNotificationIcon = (type: string) => {
    switch (type) {
      case 'new_trade': return '💰';
      case 'trade': return '💰';
      case 'error': return '❌';
      case 'info': return 'ℹ️';
      default: return '📌';
    }
  };

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 text-gray-300 hover:text-white"
      >
        {notifications.length > 0 ? <BsBellFill size={20} /> : <BsBell size={20} />}
        {notifications.length > 0 && (
          <span className="absolute top-0 right-0 inline-flex items-center justify-center px-2 py-1 text-xs font-bold leading-none text-white transform translate-x-1/2 -translate-y-1/2 bg-red-600 rounded-full">
            {notifications.length}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-96 bg-gray-800 rounded-lg shadow-lg z-50 max-h-[80vh] overflow-y-auto">
          <div className="p-4">
            <h3 className="text-lg font-semibold text-white mb-4">Уведомления</h3>
            {notifications.length > 0 ? (
              notifications.map((notification) => (
                <div
                  key={notification.id}
                  className={`mb-4 p-3 bg-gray-700 rounded-lg border-l-4 
                    ${notification.type === 'error' ? 'border-red-500' : 
                    notification.type === 'trade' ? 'border-green-500' : 
                    'border-blue-500'}`}
                >
                  <div className="flex items-start gap-2">
                    <span>{getNotificationIcon(notification.type)}</span>
                    <div className="text-white">{notification.message}</div>
                  </div>
                  <div className="text-xs text-gray-400 mt-2">
                    {notification.timestamp.toLocaleString()}
                  </div>
                </div>
              ))
            ) : (
              <div className="text-gray-400 text-center">Нет уведомлений</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
