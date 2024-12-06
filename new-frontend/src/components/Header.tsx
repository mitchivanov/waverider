import React from 'react';
import { NotificationBell } from './NotificationBell';
import { useNotifications } from '../contexts/NotificationContext';
import { useAuth } from '../contexts/AuthContext';

export const Header: React.FC = () => {
  const { notifications } = useNotifications();
  const { logout } = useAuth();

  return (
    <header className="fixed top-0 left-0 w-full bg-almostBlack text-almostWhite shadow-md z-50">
      <div className="max-w-7xl mx-auto px-4 py-3 flex justify-between items-center">
        <h1 className="text-xl font-bold">Trading Bot Dashboard</h1>
        <div className="flex items-center space-x-6">
          <nav>
            <ul className="flex space-x-4">
              <li><a href="#control" className="hover:text-green-400">Smooth</a></li>
              <li><a href="#status" className="hover:text-green-400">Operator</a></li>
              <li><a href="#orders" className="hover:text-green-400">Rebell</a></li>
              <li><a href="#trades" className="hover:text-green-400">Yel</a></li>
            </ul>
          </nav>
          <NotificationBell notifications={notifications} />
          <button
            onClick={logout}
            className="px-3 py-1 text-sm bg-red-600 hover:bg-red-700 rounded-md"
          >
            Выйти
          </button>
        </div>
      </div>
    </header>
  );
};