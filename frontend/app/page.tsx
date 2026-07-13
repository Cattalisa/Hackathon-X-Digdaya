'use client';

import React, { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { ArrowUpRight, ArrowDownRight, Terminal, Activity, BrainCircuit, MessageSquare, Search, Newspaper } from 'lucide-react';

const ReactApexChart = dynamic(() => import('react-apexcharts'), { ssr: false });

export default function NusaTerminal() {
  const [marketData, setMarketData] = useState<any[]>([]);
  const [topMovers, setTopMovers] = useState<any>({ gainers: [], losers: [], active: [] });
  const [currentTime, setCurrentTime] = useState<string>('');
  
  // Interactive States
  const [selectedSymbol, setSelectedSymbol] = useState<string>('BBCA.JK');
  const [chartPeriod, setChartPeriod] = useState<string>('1d'); // 1d, 5d, 1mo
  const [chartData, setChartData] = useState<any[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  
  // Real Data states
  const [quantSignals, setQuantSignals] = useState<any[]>([]);
  const [newsData, setNewsData] = useState<any[]>([]);

  // Chat State
  const [chatHistory, setChatHistory] = useState<{role: string, content: string}[]>([
    {role: 'assistant', content: 'System initialized. Market data loaded. How can I assist your trading today?'}
  ]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);

  const handleChatSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if(!chatInput.trim() || chatLoading) return;

    const userMessage = chatInput.trim();
    setChatInput('');
    setChatHistory(prev => [...prev, {role: 'user', content: userMessage}]);
    setChatLoading(true);

    try {
      const res = await fetch('http://127.0.0.1:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage })
      });
      const data = await res.json();
      setChatHistory(prev => [...prev, {role: 'assistant', content: data.response || 'No response'}]);
    } catch (err) {
      setChatHistory(prev => [...prev, {role: 'assistant', content: 'Error connecting to AI backend.'}]);
    } finally {
      setChatLoading(false);
    }
  };

  const fetchMarketData = async () => {
    try {
      // 1. Fetch Watchlist
      const res = await fetch('http://127.0.0.1:8000/api/market?symbols=BBCA.JK,BBRI.JK,BMRI.JK,BBNI.JK,TLKM.JK,ASII.JK,GOTO.JK,AMMN.JK,BREN.JK');
      const data = await res.json();
      setMarketData(data); // FIX: `data` is the array, not `data.data`
      
      // 2. Fetch Top Movers for the Ticker (so it's not empty!)
      const resMovers = await fetch('http://127.0.0.1:8000/api/market/movers');
      const moversData = await resMovers.json();
      setTopMovers(moversData);

      // 3. Fetch Latest News
      try {
        const resNews = await fetch('http://127.0.0.1:8000/api/news?limit=10');
        if (resNews.ok) {
          const news = await resNews.json();
          setNewsData(news);
        }
      } catch (e) {}
    } catch (error) {
      console.error('Error fetching market data', error);
    }
  };

  const fetchSignals = async () => {
    try {
      const resSignals = await fetch('http://127.0.0.1:8000/api/signals');
      if (resSignals.ok) {
        const signalsData = await resSignals.json();
        setQuantSignals(signalsData);
      }
    } catch (e) {}
  };

  const fetchChartData = async (symbol: string, period: string) => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/market/historical/${symbol}?period=${period}`);
      if (!res.ok) return;
      const data = await res.json();
      
      // Format for ApexCharts Candlestick
      const formattedData = data.map((d: any) => {
        const dateStr = d.Date || d.index || d.Datetime;
        const dateObj = new Date(dateStr);
        return {
          x: dateObj.getTime(),
          y: [d.Open, d.High, d.Low, d.Close]
        };
      });
      setChartData([{ data: formattedData }]);
    } catch (error) {
      console.error('Error fetching chart data', error);
    }
  };

  useEffect(() => {
    fetchMarketData();
    fetchSignals();
    const interval = setInterval(fetchMarketData, 15000); // 15 seconds polling
    const signalInterval = setInterval(fetchSignals, 120000); // 120 seconds polling
    
    // Realtime clock
    const clockInterval = setInterval(() => {
      const now = new Date();
      const y = now.getFullYear();
      const m = String(now.getMonth() + 1).padStart(2, '0');
      const d = String(now.getDate()).padStart(2, '0');
      const h = String(now.getHours()).padStart(2, '0');
      const min = String(now.getMinutes()).padStart(2, '0');
      const s = String(now.getSeconds()).padStart(2, '0');
      setCurrentTime(`${y}-${m}-${d} ${h}:${min}:${s} WIB`);
    }, 1000);

    return () => {
      clearInterval(interval);
      clearInterval(signalInterval);
      clearInterval(clockInterval);
    };
  }, []);

  useEffect(() => {
    fetchChartData(selectedSymbol, chartPeriod);
  }, [selectedSymbol, chartPeriod]);

  // Search functionality
  const handleSearchSubmit = async (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && searchQuery.trim()) {
      let sym = searchQuery.trim().toUpperCase();
      if (!sym.endsWith('.JK')) sym += '.JK';
      
      setSelectedSymbol(sym);
      
      // Fetch market data for this symbol to add to watchlist if not present
      if (!marketData.find(d => d.symbol === sym)) {
        try {
          const res = await fetch(`http://127.0.0.1:8000/api/market?symbols=${sym}`);
          const data = await res.json();
          if (data && data.length > 0) {
            setMarketData(prev => [data[0], ...prev]);
          }
        } catch (error) {
          console.error('Error fetching searched symbol', error);
        }
      }
      setSearchQuery('');
    }
  };

  const filteredWatchlist = marketData.filter(d => 
    d.symbol.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // ApexCharts Config
  const chartOptions: any = {
    chart: {
      type: 'candlestick',
      background: 'transparent',
      toolbar: { show: false },
      animations: { enabled: false }
    },
    theme: { mode: 'dark' },
    plotOptions: {
      candlestick: {
        colors: {
          upward: '#CCFF00', // Acid Green
          downward: '#FF3333' // Vermilion Red
        },
        wick: { useFillColor: true }
      }
    },
    xaxis: {
      type: 'datetime',
      labels: { 
        datetimeUTC: false, // Forces rendering in local time instead of UTC
        style: { colors: '#888', fontFamily: 'monospace' } 
      },
      axisBorder: { show: false },
      axisTicks: { show: false }
    },
    yaxis: {
      tooltip: { enabled: true },
      labels: { 
        style: { colors: '#888', fontFamily: 'monospace' },
        formatter: (val: number) => (val !== null && val !== undefined) ? val.toLocaleString('id-ID') : ''
      }
    },
    grid: {
      borderColor: 'rgba(255,255,255,0.05)',
      strokeDashArray: 4,
    }
  };

  // Helper to compile all items for the marquee
  const marqueeItems = [
    { label: 'IHSG', price: '7,321.45', change: '+0.5%', up: true },
    { label: 'LQ45', price: '980.20', change: '-0.1%', up: false },
    ...topMovers.gainers.map((g: any) => ({ label: g.symbol.replace('.JK',''), price: g.price.toLocaleString(), change: `+${g.change_percent.toFixed(2)}%`, up: true })),
    ...topMovers.losers.map((l: any) => ({ label: l.symbol.replace('.JK',''), price: l.price.toLocaleString(), change: `${l.change_percent.toFixed(2)}%`, up: false }))
  ];

  // Dynamic Market Status (IDX: Mon-Fri 09:00 - 16:15 WIB)
  const getMarketStatus = () => {
    const now = new Date();
    // Get time in Jakarta
    const jktTime = new Date(now.toLocaleString("en-US", {timeZone: "Asia/Jakarta"}));
    const day = jktTime.getDay();
    const hours = jktTime.getHours();
    const minutes = jktTime.getMinutes();
    
    if (day === 0 || day === 6) return false; // Weekend
    
    const timeNum = hours * 100 + minutes;
    if (timeNum >= 900 && timeNum <= 1615) return true;
    return false;
  };
  const isMarketOpen = getMarketStatus();

  return (
    <div className="min-h-screen flex flex-col font-sans">
      {/* TOP TICKER */}
      <div className="h-10 bg-primary/20 border-b border-primary/30 flex items-center overflow-hidden px-4 text-primary font-mono text-sm whitespace-nowrap">
        <div className="flex animate-marquee gap-8">
          {marqueeItems.map((item, i) => (
             <span key={i} className={item.up ? 'text-primary' : 'text-destructive'}>
               {item.label}: {item.price} {item.up ? '▲' : '▼'} {item.change}
             </span>
          ))}
          {/* Duplicate for seamless infinite loop */}
          {marqueeItems.map((item, i) => (
             <span key={`dup-${i}`} className={item.up ? 'text-primary' : 'text-destructive'}>
               {item.label}: {item.price} {item.up ? '▲' : '▼'} {item.change}
             </span>
          ))}
        </div>
      </div>

      {/* HEADER & SEARCH BAR */}
      <header className="px-6 py-4 flex justify-between items-center border-b border-white/5 bg-black/40 backdrop-blur-md sticky top-0 z-10">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary/10 border border-primary/30 flex items-center justify-center">
              <Terminal className="text-primary w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-white">NusaTerminal</h1>
              <p className="text-xs text-muted-foreground flex items-center gap-1 font-mono">
                <span className="w-2 h-2 rounded-full bg-primary animate-pulse"></span>
                SYSTEM ONLINE | {currentTime || 'SYNCING...'}
              </p>
            </div>
          </div>
          
          {/* SEARCH BAR */}
          <div className="hidden md:flex items-center relative">
            <Search className="w-4 h-4 text-muted-foreground absolute left-3" />
            <label htmlFor="emiten-search" className="sr-only">Cari emiten</label>
              <input 
                id="emiten-search"
                type="text" 
                placeholder="Cari emiten (ex: BBCA) + Enter..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={handleSearchSubmit}
                className="bg-white/5 border border-white/10 rounded-full py-1.5 pl-9 pr-4 text-sm text-white placeholder:text-muted-foreground focus:outline-none focus:border-primary/50 font-mono w-64 transition-all"
              />
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="glass-panel px-4 py-1.5 flex items-center gap-2">
            <Activity className={`w-4 h-4 ${isMarketOpen ? 'text-primary animate-pulse' : 'text-muted-foreground'}`} />
            <span className={`text-sm font-mono ${isMarketOpen ? 'text-white' : 'text-muted-foreground'}`}>
              MARKET {isMarketOpen ? 'OPEN' : 'CLOSED'}
            </span>
          </div>
        </div>
      </header>

      {/* MAIN LAYOUT */}
      <a href="#main-content" className="sr-only focus:not-sr-only focus:absolute focus:p-2 focus:bg-primary focus:text-black focus:z-50">Skip to main content</a>
      <main id="main-content" className="flex-1 p-6 grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* LEFT COLUMN: Watchlist & News */}
        <div className="lg:col-span-3 flex flex-col gap-6">
          {/* Watchlist */}
          <section aria-label="Watchlist" className="glass-panel p-4 flex-1 overflow-y-auto max-h-[400px]">
            <h2 className="text-sm font-semibold text-muted-foreground mb-4 uppercase tracking-wider flex items-center gap-2">
              <Activity className="w-4 h-4" /> Watchlist
            </h2>
            <div className="flex flex-col gap-3">
              {filteredWatchlist.length === 0 ? (
                <div className="text-muted-foreground text-sm font-mono text-center py-4">No data available</div>
              ) : (
                filteredWatchlist.map((d, i) => (
                  <button 
                    key={i} 
                    onClick={() => setSelectedSymbol(d.symbol)}
                    aria-label={`Pilih ${d.symbol}`}
                    className={`w-full text-left flex justify-between items-center p-3 rounded-lg hover:bg-white/10 transition-colors border group cursor-pointer ${selectedSymbol === d.symbol ? 'bg-white/10 border-primary/30' : 'bg-white/5 border-white/5'}`}
                  >
                    <div>
                      <div className={`font-mono font-bold transition-colors ${selectedSymbol === d.symbol ? 'text-primary' : 'text-white group-hover:text-primary'}`}>
                        {d.symbol.replace('.JK', '')}
                      </div>
                      <div className="text-xs text-muted-foreground">Vol: {(d.volume / 1000000).toFixed(1)}M</div>
                    </div>
                    <div className="text-right">
                      <div className="font-mono text-white">{d.price.toLocaleString('id-ID')}</div>
                      <div className={`text-xs flex items-center justify-end font-mono ${d.change_percent >= 0 ? 'text-primary' : 'text-destructive'}`}>
                        {d.change_percent >= 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                        {d.change_percent >= 0 ? '+' : ''}{d.change_percent?.toFixed(2) || '0.0'}%
                      </div>
                    </div>
                  </button>
                ))
              )}
            </div>
          </section>

          {/* Market News */}
          <section aria-label="Latest News" className="glass-panel p-4 flex-1 overflow-y-auto max-h-[400px] border-amber-500/20">
            <h2 className="text-sm font-semibold text-muted-foreground mb-4 uppercase tracking-wider flex items-center gap-2">
              <Newspaper className="w-4 h-4 text-amber-500/70" /> Latest News
            </h2>
            <div className="flex flex-col gap-4">
              {newsData.length === 0 ? (
                <div className="text-muted-foreground text-sm font-mono text-center py-4">Loading news...</div>
              ) : (
                newsData.map((news, i) => (
                  <a key={i} href={news.url} target="_blank" rel="noreferrer" className="block p-3 rounded-lg bg-white/5 hover:bg-white/10 transition-colors border border-white/5 cursor-pointer">
                    <h3 className="text-sm text-white font-bold leading-tight mb-2 line-clamp-2">{news.title}</h3>
                    <div className="flex justify-between items-center text-xs text-muted-foreground font-mono">
                      <span>{news.source}</span>
                      <span className={news.sentiment_score > 0 ? 'text-primary' : news.sentiment_score < 0 ? 'text-destructive' : ''}>
                        Sentimen: {news.sentiment_score > 0 ? 'Positif' : news.sentiment_score < 0 ? 'Negatif' : 'Netral'}
                      </span>
                    </div>
                  </a>
                ))
              )}
            </div>
          </section>
        </div>

        {/* CENTER COLUMN: Chart & Quant */}
        <div className="lg:col-span-6 flex flex-col gap-6">
          <div className="glass-panel p-4 h-[450px] flex flex-col relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-b from-primary/5 to-transparent pointer-events-none z-0"></div>
            <div className="flex justify-between items-center mb-2 relative z-10">
              <div>
                <h2 className="text-lg font-bold text-white uppercase tracking-wider flex items-center gap-2">
                  {selectedSymbol.replace('.JK', '')}
                  <span className="text-xs font-mono bg-white/10 px-2 py-0.5 rounded text-muted-foreground">IDX</span>
                </h2>
              </div>
              <div className="flex gap-2">
                <button 
                  onClick={() => setChartPeriod('1d')}
                  aria-pressed={chartPeriod === '1d'}
                  className={`px-3 py-1 text-xs rounded font-mono transition-colors ${chartPeriod === '1d' ? 'bg-primary/20 text-primary border border-primary/30' : 'hover:bg-white/10 text-muted-foreground border border-transparent'}`}
                >1D</button>
                <button 
                  onClick={() => setChartPeriod('5d')}
                  aria-pressed={chartPeriod === '5d'}
                  className={`px-3 py-1 text-xs rounded font-mono transition-colors ${chartPeriod === '5d' ? 'bg-primary/20 text-primary border border-primary/30' : 'hover:bg-white/10 text-muted-foreground border border-transparent'}`}
                >1W</button>
                <button 
                  onClick={() => setChartPeriod('1mo')}
                  aria-pressed={chartPeriod === '1mo'}
                  className={`px-3 py-1 text-xs rounded font-mono transition-colors ${chartPeriod === '1mo' ? 'bg-primary/20 text-primary border border-primary/30' : 'hover:bg-white/10 text-muted-foreground border border-transparent'}`}
                >1M</button>
              </div>
            </div>
            
            {/* APEX CHARTS CANDLESTICK */}
            <div className="flex-1 relative z-10 -ml-4">
              {chartData.length > 0 ? (
                 <ReactApexChart 
                   options={chartOptions} 
                   series={chartData} 
                   type="candlestick" 
                   height="100%" 
                 />
              ) : (
                <div className="w-full h-full flex items-center justify-center font-mono text-muted-foreground animate-pulse">
                  Loading Chart Data...
                </div>
              )}
            </div>
          </div>

          {/* AI QUANT SIGNALS */}
          <section aria-label="Quant AI Signals" className="glass-panel p-4 flex-1">
            <h2 className="text-sm font-semibold text-muted-foreground mb-4 uppercase tracking-wider flex items-center gap-2">
              <BrainCircuit className="w-4 h-4 text-primary" /> Quant AI Signals
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-white/10 text-muted-foreground font-mono">
                    <th scope="col" className="pb-3 font-normal">ASSET</th>
                    <th scope="col" className="pb-3 font-normal">SIGNAL</th>
                    <th scope="col" className="pb-3 font-normal">TARGET</th>
                    <th scope="col" className="pb-3 font-normal">AI RATIONALE</th>
                  </tr>
                </thead>
                <tbody className="font-mono">
                  {quantSignals.length > 0 ? (
                    quantSignals.slice(0, 5).map((s, i) => {
                      const isBuy = s.signal.includes('BUY');
                      const isSell = s.signal.includes('SELL');
                      return (
                        <tr key={i} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                          <td className="py-4 text-white font-bold">{s.symbol.replace('.JK', '')}</td>
                          <td className="py-4">
                            <span className={`px-2 py-1 rounded text-xs font-bold ${isBuy ? 'bg-primary/20 text-primary' : isSell ? 'bg-destructive/20 text-destructive' : 'bg-white/20 text-white'}`}>
                              {s.signal.replace('_', ' ')}
                            </span>
                          </td>
                          <td className="py-4 text-white">
                            {s.target_price.toLocaleString('id-ID')}
                            <div className="text-[10px] text-muted-foreground mt-1">
                              RR: {s.risk_reward_ratio} | SL: {s.stop_loss.toLocaleString('id-ID')}
                            </div>
                          </td>
                          <td className="py-4 text-muted-foreground text-xs font-sans" title={s.reasoning}>
                            {s.reasoning.length > 80 ? s.reasoning.substring(0, 80) + '...' : s.reasoning}
                          </td>
                        </tr>
                      )
                    })
                  ) : (
                    <tr>
                      <td colSpan={4} className="py-4 text-center text-muted-foreground font-mono animate-pulse">Loading Quant Signals...</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </div>

        {/* RIGHT COLUMN: Chatbot Terminal */}
        <div className="lg:col-span-3 flex flex-col gap-6">
          <div className="glass-panel flex-1 flex flex-col overflow-hidden relative min-h-[600px]">
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-primary via-primary/50 to-transparent"></div>
            <div className="p-4 border-b border-white/5 flex items-center gap-2 bg-black/20">
              <MessageSquare className="w-4 h-4 text-primary" />
              <h2 className="text-sm font-semibold text-white uppercase tracking-wider font-mono">Nusa AI Agent</h2>
            </div>
            <div className="flex-1 p-4 overflow-y-auto flex flex-col gap-4">
              {chatHistory.map((msg, i) => (
                msg.role === 'user' ? (
                  <div key={i} className="flex justify-end">
                    <div className="bg-primary/20 border border-primary/30 rounded-lg p-3 text-sm text-white">
                      {msg.content}
                    </div>
                  </div>
                ) : (
                  <div key={i} className="bg-white/5 border border-white/10 rounded-lg p-3 text-sm text-white font-mono">
                    {i === 0 ? (
                      <><span className="text-primary">{'>'}</span> {msg.content}</>
                    ) : (
                      <>
                        <div className="font-mono text-primary mb-2 flex items-center gap-2">
                           <BrainCircuit className="w-3 h-3"/> AI Analysis
                        </div>
                        {msg.content}
                      </>
                    )}
                  </div>
                )
              ))}
              {chatLoading && (
                <div className="bg-white/5 border border-white/10 rounded-lg p-3 text-sm text-white font-mono">
                  <span className="text-primary animate-pulse">{'>'}</span> Analyzing...
                </div>
              )}
            </div>
            <form onSubmit={handleChatSubmit} className="p-4 border-t border-white/5 bg-black/40 relative">
              <label htmlFor="chat-input" className="sr-only">Kirim pesan ke AI</label>
              <span className="absolute left-7 top-6 text-primary font-mono">{'>'}</span>
              <input 
                id="chat-input"
                type="text" 
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Ask AI..." 
                className="w-full bg-black/50 border border-white/10 rounded-lg py-2 pl-8 pr-4 text-sm text-white placeholder:text-white/20 focus:outline-none focus:border-primary/50 font-mono transition-colors"
                disabled={chatLoading}
              />
            </form>
          </div>
        </div>
      </main>
      
      {/* Marquee Animation in Global CSS */}
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes marquee {
          0% { transform: translateX(0%); }
          100% { transform: translateX(-50%); }
        }
        .animate-marquee {
          animation: marquee 30s linear infinite;
          width: max-content;
        }
      `}} />
    </div>
  );
}
