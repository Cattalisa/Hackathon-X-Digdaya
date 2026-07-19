import React from 'react';

interface QuickLinksCardProps {
  setChatInput: (val: string) => void;
}

export const QuickLinksCard: React.FC<QuickLinksCardProps> = ({ setChatInput }) => {
  const quickLinks = [
    { label: 'Istilah Finansial', prompt: 'Tolong jelaskan istilah finansial penting di pasar modal untuk pemula.' },
    { label: 'Edukasi Emiten', prompt: 'Apa saja kriteria emiten bank yang baik untuk investasi jangka panjang?' },
    { label: 'Analisis Fundamental', prompt: 'Bagaimana cara membaca laporan keuangan (Laba/Rugi, Neraca) secara sederhana?' },
    { label: 'Panduan Teknikal', prompt: 'Jelaskan cara menggunakan indikator MACD dan RSI untuk menentukan sinyal beli/jual.' },
    { label: 'Manajemen Risiko', prompt: 'Bagaimana cara mengatur porsi dana dan risk-to-reward ratio yang aman?' }
  ];

  return (
    <div className="bg-[#10151199] border border-[#1e2621] rounded-[10px] p-[14px]">
      <div className="text-[11px] text-[#8a958c] tracking-[0.6px] mb-[10px] font-semibold flex items-center gap-[6px]">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#22e07a" strokeWidth="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
        LITERASI QUICK-LINK
      </div>
      
      {quickLinks.map((link, index) => (
        <div 
          key={index}
          onClick={() => setChatInput(link.prompt)}
          className={`flex items-center justify-between p-[10px_4px] text-[11.5px] text-[#8a958c] cursor-pointer hover:text-[#eef2ee] transition-colors border-t border-[#1e2621] ${index === 0 ? 'first:border-t-0' : ''}`}
        >
          {link.label} <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="opacity-50 w-[12px] h-[12px]"><path d="m9 18 6-6-6-6"/></svg>
        </div>
      ))}
    </div>
  );
};
