import React from 'react';

interface CompositeScoreCardProps {
  activeSignal?: any;
}

export const CompositeScoreCard: React.FC<CompositeScoreCardProps> = ({ activeSignal }) => {
  // Hitung score 0-100 dari -1.0 to 1.0
  const rawScore = activeSignal?.composite_score ?? 0;
  // Convert -1 -> 0, 0 -> 50, +1 -> 100
  const displayScore = Math.round(((rawScore + 1) / 2) * 100);
  
  // Tentukan warna berdasarkan sinyal
  let color = '#8a958c'; // Hold
  let text = 'HOLD';
  
  if (activeSignal?.signal === 'strong_buy') {
    color = '#22e07a';
    text = 'STRONG BUY';
  } else if (activeSignal?.signal === 'buy') {
    color = '#81e263';
    text = 'BUY';
  } else if (activeSignal?.signal === 'sell') {
    color = '#e25c5c';
    text = 'SELL';
  } else if (activeSignal?.signal === 'strong_sell') {
    color = '#ff3b3b';
    text = 'STRONG SELL';
  }

  // Hitung stroke dasharray untuk progress circle (maksimum 326.7)
  const dashOffset = 326.7 - (326.7 * (displayScore / 100));

  return (
    <div className="bg-[#10151199] border border-[#1e2621] rounded-[10px] p-[14px]">
      <div className="text-[11px] text-[#8a958c] tracking-[0.6px] mb-[12px] font-semibold">COMPOSITE SCORE</div>
      <div className="flex flex-col items-center gap-[8px]">
        <div className="relative w-[120px] h-[120px]">
          <svg width="120" height="120" viewBox="0 0 120 120" className="-rotate-90 transform">
            <circle cx="60" cy="60" r="52" fill="none" stroke="#1a201b" strokeWidth="9"/>
            <circle cx="60" cy="60" r="52" fill="none" stroke={color} strokeWidth="9"
              strokeLinecap="round"
              strokeDasharray="326.7" strokeDashoffset={dashOffset}
              style={{ filter: `drop-shadow(0 0 6px ${color}99)` }}/>
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <div className="text-[30px] font-bold" style={{ color: color, textShadow: `0 0 18px ${color}55`}}>{displayScore}</div>
          </div>
        </div>
        <div className="text-[11px] font-bold tracking-[0.6px]" style={{ color: color }}>{text}</div>
      </div>
    </div>
  );
};
