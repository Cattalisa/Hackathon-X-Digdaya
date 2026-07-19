import React, { useState, useEffect } from 'react';
import { Search, Bell, Settings } from 'lucide-react';

interface TopBarProps {
  onSearch: (symbol: string) => void;
}

/**
 * TopBar Component
 * 
 * Displays the application logo, global search input, and market ticker (IHSG / Movers).
 * 
 * @param {Function} onSearch - Callback function triggered when a user searches for a stock symbol.
 * @param {Object} topMovers - Object containing 'gainers' and 'losers' arrays fetched from the API.
 */
export const TopBar: React.FC<TopBarProps> = ({ onSearch }) => {
  const [searchInput, setSearchInput] = useState('');
  const [currentTime, setCurrentTime] = useState('');

  // Clock effect
  useEffect(() => {
    const clockInterval = setInterval(() => {
      const now = new Date();
      const h = String(now.getHours()).padStart(2, '0');
      const min = String(now.getMinutes()).padStart(2, '0');
      const s = String(now.getSeconds()).padStart(2, '0');
      setCurrentTime(`${h}:${min}:${s}`);
    }, 1000);
    return () => clearInterval(clockInterval);
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && searchInput.trim()) {
      onSearch(searchInput.trim());
      setSearchInput('');
    }
  };

  return (
    <div className="flex items-center px-[18px] border-b border-[#1e2621] gap-[20px] h-[52px]">
      {/* Logo */}
      <div className="font-bold tracking-[0.5px] text-[#ffff] text-[15px] whitespace-nowrap">
        NUSA TERMINAL
      </div>

      {/* Search Wrap */}
      <div className="flex-1 max-w-[420px] flex items-center bg-[#12171388] border border-[#1e2621] rounded-[6px] px-[10px] py-[6px] gap-[8px] text-[#8a958c]">
        <Search className="w-[13px] h-[13px]" />
        <input
          type="text"
          placeholder="Cari Saham [ BBCA | Q ] lalu tekan Enter"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          onKeyDown={handleKeyDown}
          className="bg-transparent border-none outline-none text-[#eef2ee] text-[12.5px] flex-1 placeholder:text-[#5b655d]"
        />
        <span className="text-[10px] text-[#5b655d] border border-[#1e2621] rounded-[4px] px-[5px] py-[1px]">ENTER</span>
      </div>

      {/* IHSG & Clock Ticker */}
      <div className="ml-auto flex items-center gap-[8px] text-[13px] whitespace-nowrap">
        <span className="text-[#8a958c] font-mono text-[11px] mr-2">{currentTime} WIB</span>
        IHSG <span>9.137,87</span> <span className="text-[#22e07a] font-semibold">(+2.87%)</span>
      </div>

      {/* Icons */}
      <div className="flex items-center gap-[16px] ml-[18px] text-[#8a958c]">
        <Bell className="w-[16px] h-[16px] cursor-pointer hover:text-[#eef2ee] transition-colors" />
        <Settings className="w-[16px] h-[16px] cursor-pointer hover:text-[#eef2ee] transition-colors" />
      </div>
    </div>
  );
};
