import React, { memo } from 'react';
import { motion } from 'framer-motion';
import { StockInfoCard } from './StockInfoCard';
import { CompositeScoreCard } from './CompositeScoreCard';
import { FactorBreakdownCard } from './FactorBreakdownCard';
import { QuickLinksCard } from './QuickLinksCard';

interface LeftPanelProps {
  stockInfo: any;
  activeSignal?: any;
  setChatInput: (val: string) => void;
}

const COMPANY_MAP: Record<string, any> = {
  'BBCA': { name: 'Bank Central Asia', suffix: 'Tbk.', sector: 'Finance', industry: 'Banking' },
  'BBRI': { name: 'Bank Rakyat Indonesia', suffix: 'Tbk.', sector: 'Finance', industry: 'Banking' },
  'BMRI': { name: 'Bank Mandiri', suffix: 'Tbk.', sector: 'Finance', industry: 'Banking' },
  'BBNI': { name: 'Bank Negara Indonesia', suffix: 'Tbk.', sector: 'Finance', industry: 'Banking' },
  'TLKM': { name: 'Telkom Indonesia', suffix: 'Tbk.', sector: 'Infrastructure', industry: 'Telecom' },
  'ASII': { name: 'Astra International', suffix: 'Tbk.', sector: 'Consumer Cycl.', industry: 'Automotive' },
  'GOTO': { name: 'GoTo Gojek Tokopedia', suffix: 'Tbk.', sector: 'Technology', industry: 'Software' },
  'AMMN': { name: 'Amman Mineral', suffix: 'Tbk.', sector: 'Basic Materials', industry: 'Mining' },
  'BREN': { name: 'Barito Renewables', suffix: 'Tbk.', sector: 'Energy', industry: 'Alternative Energy' },
};

/**
 * LeftPanel Component
 * 
 * Aggregates all Left Panel cards into one column.
 */
export const LeftPanel: React.FC<LeftPanelProps> = memo(({ stockInfo, activeSignal, setChatInput }) => {
  const symbol = stockInfo?.symbol ? stockInfo.symbol.replace('.JK', '') : 'BBCA';
  const price = stockInfo?.price || 0;
  const change = stockInfo?.change_percent || 0;
  const isUp = change >= 0;

  const info = COMPANY_MAP[symbol] || { name: 'Perusahaan', suffix: 'Tbk.', sector: 'Unknown', industry: 'Unknown' };

  return (
    <motion.div 
      key={symbol}
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.4 }}
      className="border-r border-[#1e2621] p-[14px] flex flex-col gap-[12px] overflow-y-auto"
    >
      <StockInfoCard symbol={symbol} info={info} price={price} change={change} isUp={isUp} />
      <CompositeScoreCard activeSignal={activeSignal} />
      <FactorBreakdownCard activeSignal={activeSignal} />
      
      <QuickLinksCard setChatInput={setChatInput} />
      
      {/* Status Card */}
      <div className="flex flex-col gap-[10px]">
        <div className="flex items-center gap-[7px] text-[11px] text-[#8a958c]">
          <span className="w-[7px] h-[7px] rounded-full bg-[#22e07a] shadow-[0_0_8px_rgba(34,224,122,0.35)]"></span> 
          Nusa Pro Active
        </div>
      </div>
    </motion.div>
  );
});
LeftPanel.displayName = 'LeftPanel';
