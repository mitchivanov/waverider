import React from 'react';

interface SidebarProps {
  bots: string[];
  selectedBot: string | null;
  onSelectBot: (bot: string) => void;
  onAddBot: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ bots, selectedBot, onSelectBot, onAddBot }) => {
  return (
    <div className="sidebar bg-gray-900 text-white w-64 p-4">
      <ul className="space-y-2">
        {bots.map((bot, index) => (
          <li
            key={index}
            className={`p-2 rounded cursor-pointer ${
              selectedBot === bot ? 'bg-gray-700' : 'hover:bg-gray-800'
            }`}
            onClick={() => onSelectBot(bot)}
          >
            {bot}
          </li>
        ))}
        <li
          className="p-2 rounded cursor-pointer hover:bg-gray-800 flex justify-center items-center"
          onClick={onAddBot}
        >
          +
        </li>
      </ul>
    </div>
  );
};