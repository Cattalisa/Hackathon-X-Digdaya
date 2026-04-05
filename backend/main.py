"""
NusaTerminal - FastAPI Backend
Main entry point dengan scheduler untuk auto-refresh RAG knowledge base.
"""

import os
import math
import json
import asyncio
import logging
import threading
import schedule
import time
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from .models.schemas import (
    ChatMessage, ChatResponse, MarketData,
    SentimentAnalysis, QuantSignal, QuantDashboard
)
from .services.data_service import DataService
from .services.news_service import NewsService
from .agents.market_agent import MarketAgent
from .agents.sentiment_agent import SentimentAgent, get_sentiment_agent
from .agents.prediction_agent import QuantPredictionAgent
from .agents.chatbot import RAGChatbot

load_dotenv()


# ─── SAFE JSON ENCODER ────────────────────────────────────────────────────────
class SafeJSONEncoder(json.JSONEncoder):
    """Custom encoder yang mengganti NaN/Inf dengan null agar JSON valid."""
    def iterencode(self, o, _one_shot=False):
        return super().iterencode(self._sanitize(o), _one_shot)

    def _sanitize(self, obj):
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        elif isinstance(obj, dict):
            return {k: self._sanitize(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._sanitize(i) for i in obj]
        return obj

def safe_response(data) -> JSONResponse:
    """Kembalikan JSONResponse yang aman dari NaN/Inf."""
    clean = json.loads(json.dumps(data, cls=SafeJSONEncoder, default=str))
    return JSONResponse(content=clean)


# ─── LOGGING ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("nusaterminal")

# ─── APP ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="NusaTerminal API",
    description="Bloomberg Terminal untuk Investor Ritel Indonesia — Powered by AI",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── AGENT INSTANCES ──────────────────────────────────────────────────────────
# Inisialisasi semua agent saat startup
market_agent = MarketAgent()
sentiment_agent = get_sentiment_agent()  # Singleton — satu instance untuk seluruh app
prediction_agent = QuantPredictionAgent()
chatbot = RAGChatbot()                  # RAG-based chatbot


# ─── SCHEDULER ────────────────────────────────────────────────────────────────
def run_scheduler():
    """Background thread untuk periodic refresh."""
    interval = int(os.getenv("NEWS_REFRESH_INTERVAL_MINUTES", "15"))
    schedule.every(interval).minutes.do(chatbot.refresh_knowledge_base)
    schedule.every(interval).minutes.do(lambda: logger.info("🔄 Scheduled refresh done"))

    while True:
        schedule.run_pending()
        time.sleep(60)

@app.on_event("startup")
async def startup_event():
    """Jalankan scheduler di background thread saat startup."""
    logger.info("🚀 NusaTerminal API starting...")
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    logger.info("✅ Scheduler aktif — knowledge base akan diperbarui secara periodik")


# ─── ENDPOINTS ────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "app": "NusaTerminal API",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now()
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "sentiment_model": sentiment_agent.model_name,
        "chatbot_stats": chatbot.get_stats(),
        "timestamp": datetime.now()
    }


# ── Market Endpoints ──────────────────────────────────────────────────────────

@app.get("/api/market", response_model=List[MarketData])
def get_market_data(symbols: Optional[str] = None):
    """Ambil data pasar real-time. symbols: comma-separated, contoh: BBCA.JK,BBRI.JK"""
    symbol_list = symbols.split(",") if symbols else None
    return market_agent.get_realtime_data(symbol_list)


@app.get("/api/market/movers")
def get_top_movers():
    """Ambil top gainers, losers, dan most active."""
    return market_agent.get_top_movers()


@app.get("/api/market/all")
def get_all_assets():
    """Ambil semua aset: saham IDX, komoditas, dan indeks."""
    return market_agent.get_all_assets()


@app.get("/api/market/overview")
def get_market_overview():
    """Market overview: IHSG + breadth (jumlah saham naik/turun)."""
    return market_agent.get_market_overview()


@app.get("/api/market/watchlist")
def get_watchlist():
    """Daftar semua simbol yang tersedia per kategori."""
    return market_agent.get_watchlist()


@app.get("/api/market/info/{symbol}")
def get_symbol_info(symbol: str):
    """Informasi fundamental satu saham (sektor, PE ratio, dll)."""
    return market_agent.get_symbol_info(symbol)


@app.get("/api/news")
def get_news(limit: int = 20):
    """Ambil berita terkini dari semua sumber."""
    ns = NewsService()
    return ns.get_latest_headlines(limit=limit)


@app.get("/api/news/{symbol}")
def get_news_by_symbol(symbol: str, limit: int = 10):
    """Ambil berita yang menyebut simbol tertentu."""
    ns = NewsService()
    return ns.fetch_news_by_symbol(symbol, limit=limit)


@app.get("/api/market/ihsg")
def get_ihsg():
    """Ambil data IHSG terkini."""
    return market_agent.get_market_overview()["ihsg"]


@app.get("/api/market/historical/{symbol}")
def get_historical(symbol: str, period: str = "1mo"):
    """
    Ambil data historis OHLCV.
    period: 1d, 5d, 1mo, 3mo, 6mo, 1y
    """
    ds = DataService()
    hist = ds.get_historical_data(symbol, period)
    if hist.empty:
        raise HTTPException(status_code=404, detail=f"Data historis untuk {symbol} tidak ditemukan")
    return hist.reset_index().to_dict(orient="records")


# ── Sentiment Endpoints ───────────────────────────────────────────────────────

@app.get("/api/sentiment", response_model=List[SentimentAnalysis])
def get_sentiment(symbols: Optional[str] = None):
    """
    Analisis sentimen berita menggunakan IndoBERT AI model.
    symbols: comma-separated filter, contoh: BBCA.JK,TLKM.JK
    """
    symbol_list = symbols.split(",") if symbols else None
    return sentiment_agent.analyze_news_sentiment(symbols=symbol_list)


@app.get("/api/sentiment/dashboard")
def get_sentiment_dashboard():
    """Ringkasan sentimen semua saham untuk tampilan dashboard."""
    return sentiment_agent.get_sentiment_dashboard()


@app.get("/api/sentiment/{symbol}")
def get_symbol_sentiment(symbol: str):
    """Analisis sentimen untuk satu simbol spesifik."""
    result = sentiment_agent.analyze_single_symbol(symbol)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Tidak cukup data berita untuk analisis sentimen {symbol}"
        )
    return result


# ── Prediction Endpoints ──────────────────────────────────────────────────────

@app.get("/api/signals")
def get_signals(symbols: Optional[str] = None):
    """
    Generate sinyal quant untuk semua saham.
    Multi-factor: Technical (RSI/MACD/BB) + Momentum + Sentiment AI + Volume.
    Output: composite_score, signal, target_price, stop_loss, factor_breakdown.
    """
    symbol_list = symbols.split(",") if symbols else None
    market_data = market_agent.get_realtime_data(symbol_list)
    sentiment_data = sentiment_agent.analyze_news_sentiment(symbols=symbol_list)
    signals = prediction_agent.generate_signals(market_data, sentiment_data)
    return safe_response([s.dict() for s in signals])


@app.get("/api/signals/dashboard")
def get_quant_dashboard():
    """QuantDashboard — semua sinyal dikategorikan STRONG_BUY/BUY/HOLD/SELL/STRONG_SELL."""
    market_data = market_agent.get_realtime_data()
    sentiment_data = sentiment_agent.analyze_news_sentiment()
    dashboard = prediction_agent.get_quant_dashboard(market_data, sentiment_data)
    return safe_response(dashboard.dict())


@app.get("/api/signals/{symbol}")
def get_symbol_signal(symbol: str):
    """Analisis quant lengkap untuk satu simbol — dengan full factor breakdown."""
    market_data = market_agent.get_realtime_data([symbol])
    if not market_data or market_data[0].price <= 0:
        raise HTTPException(status_code=404, detail=f"Data untuk {symbol} tidak ditemukan")
    sentiment = sentiment_agent.analyze_single_symbol(symbol)
    result = prediction_agent.analyze_symbol(market_data[0], sentiment)
    if not result:
        raise HTTPException(status_code=422, detail=f"Data historis tidak cukup untuk {symbol}")
    return safe_response(result.dict())


# ── Chatbot Endpoints ─────────────────────────────────────────────────────────

@app.post("/api/chat", response_model=ChatResponse)
async def chat(message: ChatMessage):
    """
    RAG Chatbot endpoint.
    Menerima pesan user → retrieve konteks → generate jawaban dengan Gemini.
    """
    return await chatbot.process_message(message)


@app.post("/api/chat/refresh")
def refresh_chatbot(background_tasks: BackgroundTasks):
    """Trigger manual refresh knowledge base chatbot."""
    background_tasks.add_task(chatbot.refresh_knowledge_base)
    return {"message": "Knowledge base sedang diperbarui di background"}


@app.get("/api/chat/stats")
def get_chatbot_stats():
    """Statistik RAG system (jumlah dokumen di vector store, dll)."""
    return chatbot.get_stats()
