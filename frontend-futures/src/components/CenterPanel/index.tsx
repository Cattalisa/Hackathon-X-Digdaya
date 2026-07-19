import React, { memo } from 'react';
import { motion } from 'framer-motion';
import { InteractiveChart } from './InteractiveChart';
import { SentimentAgent } from './SentimentAgent';
import { QuantSignalsTable } from './QuantSignalsTable';

interface CenterPanelProps {
  chartData: any[];
  chartPeriod: string;
  setChartPeriod: (period: string) => void;
  targetPrice: number;
  stopLoss: number;
  news: any[];
  signals: any[];
}

/**
 * CenterPanel Component
 * 
 * Aggregates Interactive Chart, Sentiment Analysis, and Quant Signals.
 */
export const CenterPanel: React.FC<CenterPanelProps> = memo(({
  chartData,
  chartPeriod,
  setChartPeriod,
  targetPrice,
  stopLoss,
  news,
  signals
}) => {
  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="p-[14px] flex flex-col gap-[12px] overflow-y-auto border-r border-[#1e2621]"
    >
      <InteractiveChart 
        chartData={chartData} 
        chartPeriod={chartPeriod} 
        setChartPeriod={setChartPeriod} 
        targetPrice={targetPrice} 
        stopLoss={stopLoss} 
      />
      <SentimentAgent news={news} />
      <QuantSignalsTable signals={signals} />
    </motion.div>
  );
});
CenterPanel.displayName = 'CenterPanel';
