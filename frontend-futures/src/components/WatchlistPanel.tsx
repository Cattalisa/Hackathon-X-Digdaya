import { ArrowUpRight, ArrowDownRight, Activity } from 'lucide-react';

interface WatchlistPanelProps {
  watchlist: any[];
  selectedSymbol: string;
  onSelectSymbol: (symbol: string) => void;
}

/**
 * WatchlistPanel Component
 * 
 * Takes the place of the old Sidebar. Displays a list of watched stocks (banks).
 * Clicking on a stock updates the globally selected symbol.
 * 
 * @param {Array} watchlist - Array of market data for the watched symbols.
 * @param {string} selectedSymbol - Currently selected symbol (e.g. "BBCA.JK").
 * @param {Function} onSelectSymbol - Callback to change the selected symbol.
 */
export const WatchlistPanel: React.FC<WatchlistPanelProps> = ({ watchlist, selectedSymbol, onSelectSymbol }) => {
  
  return (
    <div className="border-r border-[#1e2621] p-[16px_10px] flex flex-col gap-[2px] overflow-y-auto">
      <div className="text-[10px] font-semibold text-[#5b655d] mb-[8px] px-[12px] uppercase tracking-wider flex items-center gap-2">
        <Activity className="w-3 h-3" /> WATCHLIST BANK
      </div>

      <div className="flex flex-col gap-1 mt-2">
        {watchlist.length === 0 ? (
          <div className="text-[#8a958c] text-[11px] text-center py-4 animate-pulse">Loading Watchlist...</div>
        ) : (
          watchlist.map((item, idx) => {
            const isActive = selectedSymbol === item.symbol;
            const isUp = item.change_percent >= 0;
            return (
              <button
                key={idx}
                onClick={() => onSelectSymbol(item.symbol)}
                className={`flex justify-between items-center p-[9px_12px] rounded-[6px] cursor-pointer text-left transition-all ${
                  isActive 
                    ? 'bg-gradient-to-r from-[rgba(34,224,122,0.16)] to-transparent text-[#22e07a] border-l-2 border-[#22e07a] pl-[10px]' 
                    : 'text-[#8a958c] hover:bg-[#10151199]'
                }`}
              >
                <div>
                  <div className={`font-bold text-[12.5px] ${isActive ? 'text-[#22e07a]' : 'text-[#eef2ee]'}`}>
                    {item.symbol.replace('.JK', '')}
                  </div>
                  <div className="text-[10px] text-[#5b655d] mt-[2px]">Vol: {(item.volume / 1000000).toFixed(1)}M</div>
                </div>
                <div className="text-right">
                  <div className={`font-bold text-[12.5px] ${isActive ? 'text-[#22e07a]' : 'text-[#eef2ee]'}`}>
                    {item.price.toLocaleString('id-ID')}
                  </div>
                  <div className={`text-[10.5px] flex items-center justify-end gap-1 mt-[2px] ${isUp ? 'text-[#22e07a]' : 'text-[#ff5c5c]'}`}>
                    {isUp ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                    {isUp ? '+' : ''}{item.change_percent.toFixed(2)}%
                  </div>
                </div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
};
