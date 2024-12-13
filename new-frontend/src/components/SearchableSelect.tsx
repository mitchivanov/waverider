import React, { useState, useRef, useEffect, useCallback } from 'react';

interface SearchableSelectProps {
  options: string[];
  value: string;
  onChange: (value: string, name: string) => void;
  name: string;
  placeholder: string;
  disabled?: boolean;
  apiKey?: string;
  apiSecret?: string;
}

interface Balance {
  asset: string;
  free: string;
  locked: string;
}

export const SearchableSelect: React.FC<SearchableSelectProps> = ({
  options,
  value,
  onChange,
  name,
  placeholder,
  disabled = false,
  apiKey,
  apiSecret
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState(value);
  const [balances, setBalances] = useState<Record<string, Balance>>({});
  const wrapperRef = useRef<HTMLDivElement>(null);

  const fetchBalances = useCallback(async () => {
    if (!apiKey || !apiSecret) return;
    
    try {
      const response = await fetch('http://localhost:8000/api/balance', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          api_key: apiKey,
          api_secret: apiSecret
        })
      });
      
      const data = await response.json();
      const balanceMap: Record<string, Balance> = {};
      data.balances.forEach((balance: Balance) => {
        balanceMap[balance.asset] = balance;
      });
      setBalances(balanceMap);
    } catch (error) {
      console.error('Error fetching balances:', error);
    }
  }, [apiKey, apiSecret]);

  useEffect(() => {
    if (apiKey && apiSecret) {
      fetchBalances();
    }
  }, [apiKey, apiSecret, fetchBalances]);

  const filteredOptions = options.filter(option =>
    option.toLowerCase().includes(searchTerm.toLowerCase())
  );

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    setSearchTerm(value);
  }, [value]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchTerm(e.target.value);
    setIsOpen(true);
  };

  const handleOptionClick = (option: string) => {
    onChange(option, name);
    setSearchTerm(option);
    setIsOpen(false);
  };

  return (
    <div ref={wrapperRef} className="relative">
      <input
        type="text"
        value={searchTerm}
        onChange={handleInputChange}
        onFocus={() => setIsOpen(true)}
        placeholder={placeholder}
        className="w-full px-3 py-2 bg-gray-700 text-white border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
        disabled={disabled}
      />
      {isOpen && !disabled && (
        <div className="absolute z-50 w-full mt-1 max-h-60 overflow-y-auto bg-gray-700 border border-gray-600 rounded-md shadow-lg">
          {filteredOptions.length > 0 ? (
            filteredOptions.map((option) => (
              <div
                key={option}
                className="px-3 py-2 cursor-pointer hover:bg-gray-600 text-white flex justify-between items-center"
                onClick={() => handleOptionClick(option)}
              >
                <span>{option}</span>
                {balances[option] && (
                  <span className="text-sm text-gray-400">
                    {parseFloat(balances[option].free).toFixed(8)}
                  </span>
                )}
              </div>
            ))
          ) : (
            <div className="px-3 py-2 text-gray-400">Nothing found</div>
          )}
        </div>
      )}
    </div>
  );
};
