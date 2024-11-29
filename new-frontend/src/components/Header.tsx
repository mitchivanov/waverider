import React from 'react';

export const Header: React.FC = () => {
  return (
    <header className="fixed top-0 left-0 w-full bg-almostBlack text-almostWhite shadow-md z-50">
      <div className="max-w-7xl mx-auto px-4 py-3 flex justify-between items-center">
        <h1 className="text-xl font-bold">Trading Bot Dashboard</h1>
        <nav>
          <ul className="flex space-x-4">
            <li><a href="#control" className="hover:text-green-400">Smooth</a></li>
            <li><a href="#status" className="hover:text-green-400">Operator</a></li>
            <li><a href="#orders" className="hover:text-green-400">Rebell</a></li>
            <li><a href="#trades" className="hover:text-green-400">Yel</a></li>
          </ul>
        </nav>
      </div>
    </header>
  );
};