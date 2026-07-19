import React from 'react';

interface QuantSignalsTableProps {
  signals: any[];
}

export const QuantSignalsTable: React.FC<QuantSignalsTableProps> = ({ signals }) => {
  return (
    <div className="bg-[#10151199] border border-[#1e2621] rounded-[10px] p-[14px_16px]">
      <div className="flex items-center gap-[8px] mb-[12px]">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#22e07a" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 2v20M17 12H7"/></svg>
        <span className="text-[12px] font-semibold text-[#eef2ee] flex-1">QUANT AI SIGNALS</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-[11px]">
          <thead>
            <tr className="border-b border-[#1e2621] text-[#8a958c]">
              <th className="pb-2 font-semibold">ASSET</th>
              <th className="pb-2 font-semibold">SIGNAL</th>
              <th className="pb-2 font-semibold">TARGET</th>
              <th className="pb-2 font-semibold">AI RATIONALE</th>
            </tr>
          </thead>
          <tbody>
            {signals && signals.length > 0 ? (
              signals.slice(0, 5).map((s, i) => {
                const isBuy = s.signal.includes('BUY');
                const isSell = s.signal.includes('SELL');
                return (
                  <tr key={i} className="border-b border-[#1e2621] last:border-0 hover:bg-[#12181388] transition-colors">
                    <td className="py-3 text-[#eef2ee] font-bold">{s.symbol.replace('.JK', '')}</td>
                    <td className="py-3">
                      <span className={`px-2 py-1 rounded-[4px] text-[9.5px] font-bold ${
                        isBuy ? 'bg-[rgba(34,224,122,0.14)] text-[#22e07a]' : 
                        isSell ? 'bg-[rgba(255,92,92,0.14)] text-[#ff5c5c]' : 
                        'bg-[rgba(216,178,90,0.14)] text-[#d8b25a]'
                      }`}>
                        {s.signal.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="py-3 text-[#eef2ee]">
                      {s.target_price.toLocaleString('id-ID')}
                      <div className="text-[9.5px] text-[#5b655d] mt-1">
                        RR: {s.risk_reward_ratio} | SL: {s.stop_loss.toLocaleString('id-ID')}
                      </div>
                    </td>
                    <td className="py-3 text-[#8a958c] text-[10.5px] pr-2">
                      {s.reasoning.length > 70 ? s.reasoning.substring(0, 70) + '...' : s.reasoning}
                    </td>
                  </tr>
                )
              })
            ) : (
              <tr>
                <td colSpan={4} className="py-4 text-center text-[#5b655d]">Loading Quant Signals...</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
