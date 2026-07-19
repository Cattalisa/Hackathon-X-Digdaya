import { useState, useEffect, useMemo, useCallback } from 'react'
import { TopBar } from './components/TopBar'
import { WatchlistPanel } from './components/WatchlistPanel'
import { LeftPanel } from './components/LeftPanel'
import { CenterPanel } from './components/CenterPanel'
import { RightPanel } from './components/RightPanel'

/**
 * Main Application Component (v2)
 * 
 * Manages global state (selected stock, watchlist, chart data, etc.)
 * and integrates the HTML/CSS-based layout.
 */
function App() {
  const [selectedSymbol, setSelectedSymbol] = useState<string>('BBCA.JK')
  const [chartPeriod, setChartPeriod] = useState<string>('1d')
  
  // Data States
  const [watchlist, setWatchlist] = useState<any[]>([])
  const [chartData, setChartData] = useState<any[]>([])
  const [news, setNews] = useState<any[]>([])
  const [signals, setSignals] = useState<any[]>([])
  
  const [isAppReady, setIsAppReady] = useState(false)
  
  // Chat State
  const [chatInput, setChatInput] = useState('')

  // Initial Fetch & Polling
  useEffect(() => {
    const fetchMarketData = async () => {
      try {
        // Watchlist (Basic array of symbols)
        const currentSymbols = watchlist.length > 0 
          ? watchlist.map(w => w.symbol).join(',')
          : 'BBCA.JK,BBRI.JK,BMRI.JK,BBNI.JK,TLKM.JK,ASII.JK,GOTO.JK,AMMN.JK,BREN.JK'
        
        const resMarket = await fetch(`http://127.0.0.1:8000/api/market?symbols=${currentSymbols}`)
        if (resMarket.ok) {
          const data = await resMarket.json()
          setWatchlist(data)
        }

        // News (Fetching up to 10 like old frontend)
        const resNews = await fetch('http://127.0.0.1:8000/api/news?limit=10')
        if (resNews.ok) {
          const newsData = await resNews.json()
          const formattedNews = newsData.map((n: any) => ({
            title: n.title,
            source: n.source,
            url: n.url,
            time: 'Just now',
            sentiment: n.sentiment_score > 0 ? 'POSITIVE' : (n.sentiment_score < 0 ? 'NEGATIVE' : 'NEUTRAL')
          }))
          setNews(formattedNews)
        }

        // Signals
        const resSignals = await fetch('http://127.0.0.1:8000/api/signals')
        if (resSignals.ok) setSignals(await resSignals.json())

      } catch (err) {
        console.error("Error fetching data:", err)
      }
    }

    fetchMarketData()
    const interval = setInterval(fetchMarketData, 15000) // Poll every 15s
    return () => clearInterval(interval)
  }, []) // Empty dependency, runs once + polls

  // Fetch chart data when symbol or period changes
  useEffect(() => {
    const fetchChart = async () => {
      try {
        const res = await fetch(`http://127.0.0.1:8000/api/market/historical/${selectedSymbol}?period=${chartPeriod}`)
        if (res.ok) {
          const data = await res.json()
          const formattedData = data.map((d: any) => ({
            x: new Date(String(d.Date || d.index || d.Datetime).replace(' ', 'T')).getTime(),
            y: [d.Open, d.High, d.Low, d.Close]
          }))
          setChartData([{ data: formattedData }])
        }
      } catch (err) {
        console.error("Error fetching chart:", err)
      }
    }
    fetchChart()
  }, [selectedSymbol, chartPeriod])

  // Check if App is Ready
  useEffect(() => {
    if (watchlist.length > 0 && chartData.length > 0 && signals.length > 0) {
      setIsAppReady(true)
    }
  }, [watchlist, chartData, signals])

  // Handle Search Input from TopBar
  const handleSearch = async (symbol: string) => {
    let sym = symbol.toUpperCase()
    if (!sym.endsWith('.JK')) sym += '.JK'
    
    setSelectedSymbol(sym)
    
    // Add to watchlist if not exists
    if (!watchlist.find(w => w.symbol === sym)) {
      try {
        const res = await fetch(`http://127.0.0.1:8000/api/market?symbols=${sym}`)
        if (res.ok) {
          const data = await res.json()
          if (data && data.length > 0) {
            setWatchlist(prev => [data[0], ...prev])
          }
        }
      } catch (e) {
        console.error(e)
      }
    }
  }

  const activeSignal = useMemo(() => {
    return signals.find((s: any) => s.symbol.includes(selectedSymbol.replace('.JK', ''))) || {};
  }, [signals, selectedSymbol]);
  
  const currentTargetPrice = activeSignal.target_price || 0;
  const currentStopLoss = activeSignal.stop_loss || 0;
  
  const currentStockInfo = useMemo(() => {
    return watchlist.find(w => w.symbol === selectedSymbol) || null;
  }, [watchlist, selectedSymbol]);

  // useCallback for stable reference
  const handleSetChatInput = useCallback((val: string) => setChatInput(val), []);

  if (!isAppReady) {
    return (
      <div className="h-screen w-screen bg-[#04150a] flex flex-col items-center justify-center">
        <div className="w-[40px] h-[40px] border-4 border-[#1e2621] border-t-[#22e07a] rounded-full animate-spin"></div>
        <div className="mt-[20px] text-[#22e07a] font-bold tracking-[2px] text-[14px]">MENYINKRONKAN PASAR...</div>
        <div className="mt-[8px] text-[#5b655d] text-[11px]">Memuat data Kuantitatif, Sentimen, dan Histori</div>
      </div>
    );
  }

  return (
    <div className="grid grid-rows-[52px_1fr] h-screen">
      <TopBar onSearch={handleSearch} />
      
      <div className="grid grid-cols-[190px_250px_1fr_360px] overflow-hidden">
        <WatchlistPanel 
          watchlist={watchlist} 
          selectedSymbol={selectedSymbol} 
          onSelectSymbol={setSelectedSymbol} 
        />
        <LeftPanel 
          stockInfo={currentStockInfo} 
          activeSignal={activeSignal}
          setChatInput={handleSetChatInput}
        />
        <CenterPanel 
          chartData={chartData} 
          chartPeriod={chartPeriod} 
          setChartPeriod={setChartPeriod}
          targetPrice={currentTargetPrice}
          stopLoss={currentStopLoss}
          news={news}
          signals={signals}
        />
        <RightPanel 
          selectedSymbol={selectedSymbol} 
          chatInput={chatInput}
          setChatInput={handleSetChatInput}
        />
      </div>
    </div>
  )
}

export default App
