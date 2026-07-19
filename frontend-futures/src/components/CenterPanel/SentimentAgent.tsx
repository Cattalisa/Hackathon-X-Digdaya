import React, { useState } from 'react';

interface SentimentAgentProps {
  news: any[];
}

export const SentimentAgent: React.FC<SentimentAgentProps> = ({ news }) => {
  const [newsPage, setNewsPage] = useState(1);
  const newsPerPage = 3;
  const totalNewsPages = Math.ceil(news.length / newsPerPage) || 1;
  const displayedNews = news.slice((newsPage - 1) * newsPerPage, newsPage * newsPerPage);

  return (
    <div className="bg-[#10151199] border border-[#1e2621] rounded-[10px] p-[14px_16px]">
      <div className="flex items-center justify-between mb-[12px]">
        <div className="flex items-center gap-[8px]">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#22e07a" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          <span className="text-[12px] font-semibold text-[#eef2ee]">SENTIMENT ANALYSIS AGENT</span>
        </div>
        <span className="text-[9.5px] font-bold py-[3px] px-[9px] rounded-[20px] bg-[rgba(34,224,122,0.14)] text-[#22e07a]">Positive Flow</span>
      </div>

      <div className="flex flex-col min-h-[220px]">
        {news.length === 0 ? (
          <div className="text-center py-4 text-[#8a958c] text-[11px]">No news available.</div>
        ) : (
          displayedNews.map((item, idx) => (
            <a key={idx} href={item.url} target="_blank" rel="noreferrer" className="block py-[10px] border-t border-[#1e2621] first:border-t-0 first:pt-0 cursor-pointer group hover:bg-[#12181388] transition-colors rounded-[6px] px-[8px] -mx-[8px]">
              <div className="flex justify-between items-center text-[10.5px] text-[#5b655d] mb-[6px]">
                <span>{item.source} &bull; {item.time || '10m ago'}</span>
                <span className={`text-[9.5px] font-bold py-[3px] px-[9px] rounded-[20px] ${
                  item.sentiment === 'POSITIVE' ? 'bg-[rgba(34,224,122,0.14)] text-[#22e07a]' : 
                  item.sentiment === 'NEGATIVE' ? 'bg-[rgba(255,92,92,0.14)] text-[#ff5c5c]' : 
                  'bg-[rgba(216,178,90,0.14)] text-[#d8b25a]'
                }`}>{item.sentiment}</span>
              </div>
              <div className="text-[12.5px] mb-[8px] leading-[1.4] text-[#eef2ee] group-hover:text-[#22e07a] transition-colors">{item.title}</div>
              <div className="flex justify-between items-center">
                <div className="flex gap-[6px]">
                  <span className="text-[9.5px] text-[#8a958c] bg-[#171d18] border border-[#1e2621] rounded-[4px] px-[7px] py-[2px]">Market</span>
                </div>
                <div className="text-[10.5px] text-[#22e07a] flex items-center gap-[4px]">
                  AI SUMMARY <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="m9 18 6-6-6-6"/></svg>
                </div>
              </div>
            </a>
          ))
        )}
      </div>

      {totalNewsPages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-2 pt-3 border-t border-[#1e2621]">
          <button 
            onClick={() => setNewsPage(p => Math.max(1, p - 1))}
            disabled={newsPage === 1}
            className="text-[#8a958c] hover:text-[#22e07a] disabled:opacity-30 disabled:hover:text-[#8a958c] px-2 py-1"
          >
            &lt;
          </button>
          <div className="flex gap-1">
            {Array.from({ length: totalNewsPages }).map((_, i) => (
              <button 
                key={i} 
                onClick={() => setNewsPage(i + 1)}
                className={`w-6 h-6 rounded flex items-center justify-center text-[10px] font-bold transition-colors ${
                  newsPage === i + 1 ? 'bg-[rgba(34,224,122,0.2)] text-[#22e07a]' : 'text-[#5b655d] hover:bg-[#121813] hover:text-[#8a958c]'
                }`}
              >
                {i + 1}
              </button>
            ))}
          </div>
          <button 
            onClick={() => setNewsPage(p => Math.min(totalNewsPages, p + 1))}
            disabled={newsPage === totalNewsPages}
            className="text-[#8a958c] hover:text-[#22e07a] disabled:opacity-30 disabled:hover:text-[#8a958c] px-2 py-1"
          >
            &gt;
          </button>
        </div>
      )}
    </div>
  );
};
