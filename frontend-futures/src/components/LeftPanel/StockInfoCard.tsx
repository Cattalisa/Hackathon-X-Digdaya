import React from 'react';

interface StockInfoCardProps {
  symbol: string;
  info: any;
  price: number;
  change: number;
  isUp: boolean;
}

export const StockInfoCard: React.FC<StockInfoCardProps> = ({ symbol, info, price, change, isUp }) => {
  return (
    <div className="bg-[#10151199] border border-[#1e2621] rounded-[10px] p-[14px]">
      <div className="flex justify-between items-start">
        <div className="flex-1 overflow-hidden pr-2">
          <div className="text-[16px] font-bold">{symbol}</div>
          <div className="text-[#8a958c] text-[11.5px] mt-[2px] whitespace-nowrap overflow-hidden text-ellipsis">
            {info.name}<br/>{info.suffix}
          </div>
        </div>
        <div className="shrink-0">
          <div className="text-[16px] font-bold text-right">{price.toLocaleString('id-ID')}</div>
          <div className={`text-[11.5px] text-right mt-[2px] ${isUp ? 'text-[#22e07a]' : 'text-[#ff5c5c]'}`}>
            {isUp ? '+' : ''}{change.toFixed(2)}%
          </div>
          <div className="text-[#5b655d] text-[10.5px] text-right">(Today)</div>
        </div>
      </div>
      <div className="flex gap-[8px] mt-[12px]">
        <div className="flex-1 bg-[#0d1210] border border-[#1e2621] rounded-[6px] p-[6px_8px] overflow-hidden">
          <div className="text-[9.5px] text-[#5b655d] letter-spacing-[0.4px]">SECTOR</div>
          <div className="text-[10.5px] mt-[2px] whitespace-nowrap overflow-hidden text-ellipsis">{info.sector}</div>
        </div>
        <div className="flex-1 bg-[#0d1210] border border-[#1e2621] rounded-[6px] p-[6px_8px] overflow-hidden">
          <div className="text-[9.5px] text-[#5b655d] letter-spacing-[0.4px]">INDUSTRY</div>
          <div className="text-[10.5px] mt-[2px] whitespace-nowrap overflow-hidden text-ellipsis">{info.industry}</div>
        </div>
      </div>
    </div>
  );
};
