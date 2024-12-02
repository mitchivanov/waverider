import React, { useState, useRef, useEffect } from 'react';

interface SearchableSelectProps {
  options: string[];
  value: string;
  onChange: (value: string, name: string) => void;
  name: string;
  placeholder: string;
  disabled?: boolean;
}

export const SearchableSelect: React.FC<SearchableSelectProps> = ({
  options,
  value,
  onChange,
  name,
  placeholder,
  disabled = false
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState(value);
  const wrapperRef = useRef<HTMLDivElement>(null);

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
                className="px-3 py-2 cursor-pointer hover:bg-gray-600 text-white"
                onClick={() => handleOptionClick(option)}
              >
                {option}
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
