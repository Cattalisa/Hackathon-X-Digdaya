import React from 'react';

interface FactorBreakdownCardProps {
  activeSignal?: any;
}

const getFactorColor = (score: number) => {
  if (score > 0.5) return '#22e07a';
  if (score > 0) return '#81e263';
  if (score === 0) return '#8a958c';
  if (score > -0.5) return '#e25c5c';
  return '#ff3b3b';
};

const getFactorWidth = (score: number) => {
  // -1 -> 0%, 0 -> 50%, +1 -> 100%
  return Math.round(((score + 1) / 2) * 100);
};

export const FactorBreakdownCard: React.FC<FactorBreakdownCardProps> = ({ activeSignal }) => {
  const techScore = activeSignal?.technical?.factor_score ?? 0;
  const momScore = activeSignal?.momentum?.factor_score ?? 0;
  const sentScore = activeSignal?.sentiment_score ?? 0;
  const volScore = activeSignal?.volume?.factor_score ?? 0;

  const techColor = getFactorColor(techScore);
  const momColor = getFactorColor(momScore);
  const sentColor = getFactorColor(sentScore);
  const volColor = getFactorColor(volScore);

  return (
    <div className="bg-[#10151199] border border-[#1e2621] rounded-[10px] p-[14px]">
      <div className="text-[11px] text-[#8a958c] tracking-[0.6px] mb-[12px] font-semibold">FACTOR BREAKDOWN</div>

      <div className="mb-[12px]">
        <div className="flex justify-between text-[11.5px] mb-[5px]">
          <span className="text-[#eef2ee]">Technical (30%)</span>
        </div>
        <div className="flex flex-col items-start mb-[5px] gap-[2px]">
          <span className="text-[11px] font-semibold" style={{ color: techColor }}>
            {activeSignal?.technical?.rsi_signal === 'overbought' ? 'Overbought' : activeSignal?.technical?.rsi_signal === 'oversold' ? 'Oversold' : 'Neutral'}
          </span>
          <span className="text-[#5b655d] text-[9.5px]">MACD: {activeSignal?.technical?.macd_crossover?.replace('_', ' ') || 'None'}</span>
        </div>
        <div className="h-[4px] rounded-[3px] bg-[#1a201b] overflow-hidden">
          <div className="h-full rounded-[3px] transition-all duration-500" style={{ backgroundColor: techColor, width: `${getFactorWidth(techScore)}%` }}></div>
        </div>
      </div>

      <div className="mb-[12px]">
        <div className="flex justify-between text-[11.5px] mb-[5px]">
          <span className="text-[#eef2ee]">Momentum (25%)</span>
        </div>
        <div className="flex flex-col items-start mb-[5px] gap-[2px]">
          <span className="text-[11px] font-semibold capitalize" style={{ color: momColor }}>
            {activeSignal?.momentum?.momentum_5_20 || 'Neutral'}
          </span>
        </div>
        <div className="h-[4px] rounded-[3px] bg-[#1a201b] overflow-hidden">
          <div className="h-full rounded-[3px] transition-all duration-500" style={{ backgroundColor: momColor, width: `${getFactorWidth(momScore)}%` }}></div>
        </div>
      </div>

      <div className="mb-[12px]">
        <div className="flex justify-between text-[11.5px] mb-[5px]">
          <span className="text-[#eef2ee]">Sentiment IndoBERT (25%)</span>
        </div>
        <div className="flex flex-col items-start mb-[5px] gap-[2px]">
          <span className="text-[11px] font-semibold capitalize" style={{ color: sentColor }}>
            {activeSignal?.sentiment_label || 'Neutral'}
          </span>
        </div>
        <div className="h-[4px] rounded-[3px] bg-[#1a201b] overflow-hidden">
          <div className="h-full rounded-[3px] transition-all duration-500" style={{ backgroundColor: sentColor, width: `${getFactorWidth(sentScore)}%` }}></div>
        </div>
      </div>

      <div className="mb-[0]">
        <div className="flex justify-between text-[11.5px] mb-[5px]">
          <span className="text-[#eef2ee]">Vol. Anomaly (20%)</span>
        </div>
        <div className="flex flex-col items-start mb-[5px] gap-[2px]">
          <span className="text-[11px] font-semibold capitalize" style={{ color: volColor }}>
            {activeSignal?.volume?.volume_trend || 'Normal'}
          </span>
        </div>
        <div className="h-[4px] rounded-[3px] bg-[#1a201b] overflow-hidden">
          <div className="h-full rounded-[3px] transition-all duration-500" style={{ backgroundColor: volColor, width: `${getFactorWidth(volScore)}%` }}></div>
        </div>
      </div>
    </div>
  );
};
