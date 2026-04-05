"""
NusaTerminal - Data Schemas
Pydantic models untuk semua data yang mengalir antar agent.
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict
from enum import Enum


# ─── ENUMS ────────────────────────────────────────────────────────────────────

class MarketType(str, Enum):
    STOCK = "stock"
    COMMODITY = "commodity"
    INDEX = "index"

class Sentiment(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"

class Signal(str, Enum):
    STRONG_BUY  = "strong_buy"
    BUY         = "buy"
    HOLD        = "hold"
    SELL        = "sell"
    STRONG_SELL = "strong_sell"


# ─── MARKET DATA ──────────────────────────────────────────────────────────────

class MarketData(BaseModel):
    symbol: str
    name: str
    price: float
    change: float
    change_percent: float
    volume: int
    open: float
    high: float
    low: float
    close: float
    last_update: datetime
    market_type: MarketType = MarketType.STOCK


# ─── NEWS & SENTIMENT ─────────────────────────────────────────────────────────

class NewsArticle(BaseModel):
    id: str
    title: str
    summary: str
    source: str
    url: str
    published_at: datetime
    symbols: List[str] = []
    sentiment_score: float = 0.0

class SentimentAnalysis(BaseModel):
    symbol: str
    sentiment: Sentiment
    score: float           # -1 (very bearish) sampai +1 (very bullish)
    confidence: float      # 0 sampai 1
    news_count: int
    last_updated: datetime


# ─── QUANT FACTOR BREAKDOWN ───────────────────────────────────────────────────

class TechnicalFactors(BaseModel):
    """Hasil kalkulasi indikator teknikal."""
    rsi: float                      # 0–100
    rsi_signal: str                 # "oversold" / "neutral" / "overbought"
    macd: float                     # MACD line
    macd_signal: float              # Signal line
    macd_histogram: float           # Histogram (MACD - Signal)
    macd_crossover: str             # "bullish_cross" / "bearish_cross" / "none"
    bb_upper: float                 # Bollinger Band upper
    bb_lower: float                 # Bollinger Band lower
    bb_position: float              # 0=at lower, 0.5=at middle, 1=at upper
    bb_signal: str                  # "near_lower" / "middle" / "near_upper"
    ma_20: float                    # SMA 20
    ma_50: float                    # SMA 50
    ma_trend: str                   # "above_both" / "below_both" / "mixed"
    factor_score: float             # -1 sampai +1, agregat dari semua indikator teknikal

class MomentumFactors(BaseModel):
    """Hasil kalkulasi momentum & mean reversion."""
    return_5d: float                # Return 5 hari (%)
    return_20d: float               # Return 20 hari (%)
    return_60d: float               # Return 60 hari (%)
    momentum_5_20: str              # "bullish" jika return_5d > return_20d
    z_score: float                  # Z-score harga vs MA (mean reversion signal)
    mean_reversion_signal: str      # "oversold" / "neutral" / "overbought"
    factor_score: float             # -1 sampai +1

class VolumeFactors(BaseModel):
    """Analisis anomali volume."""
    avg_volume_20d: float           # Rata-rata volume 20 hari
    volume_ratio: float             # Volume hari ini / rata-rata (>1.5 = anomali)
    volume_trend: str               # "surge" / "normal" / "dry"
    obv_trend: str                  # On-Balance Volume trend: "up" / "flat" / "down"
    factor_score: float             # -1 sampai +1


# ─── QUANT SIGNAL (OUTPUT UTAMA) ──────────────────────────────────────────────

class QuantSignal(BaseModel):
    """
    Output lengkap Quant Analysis Engine.
    Menggabungkan technical + momentum + sentiment + volume
    menjadi satu composite score dan sinyal trading.
    """
    symbol: str
    name: str
    current_price: float

    # ── Composite Score ──────────────────────────────────────────────────────
    composite_score: float          # -1 (very bearish) sampai +1 (very bullish)
    signal: Signal                  # Derived dari composite_score
    confidence: float               # 0–1, seberapa kuat sinyal

    # ── Factor Breakdown ─────────────────────────────────────────────────────
    technical: TechnicalFactors
    momentum: MomentumFactors
    volume: VolumeFactors
    sentiment_score: float          # Dari SentimentAgent (-1 sampai +1)
    sentiment_label: str            # "bullish" / "neutral" / "bearish"

    # ── Factor Weights & Contribution ────────────────────────────────────────
    factor_weights: Dict[str, float]        # Bobot tiap faktor
    factor_contributions: Dict[str, float]  # Kontribusi nyata tiap faktor ke score

    # ── Target Price & Stop Loss (ATR-based) ─────────────────────────────────
    atr: float                      # Average True Range (volatilitas)
    target_price: float             # Entry → target (risk:reward ~1:2)
    stop_loss: float                # Entry → stop (ATR * multiplier)
    risk_reward_ratio: float        # (target - price) / (price - stop_loss)
    upside_pct: float               # % potensi kenaikan ke target
    downside_pct: float             # % risiko penurunan ke stop loss

    # ── Narasi ───────────────────────────────────────────────────────────────
    reasoning: str                  # Penjelasan singkat kenapa sinyal ini
    key_risks: List[str]            # Risk utama yang harus diperhatikan
    timeframe: str                  # "3–5 hari trading"

    generated_at: datetime


# ─── PORTFOLIO SUMMARY ────────────────────────────────────────────────────────

class QuantDashboard(BaseModel):
    """Ringkasan seluruh sinyal quant untuk dashboard."""
    strong_buy: List[QuantSignal]
    buy: List[QuantSignal]
    hold: List[QuantSignal]
    sell: List[QuantSignal]
    strong_sell: List[QuantSignal]
    market_breadth: float           # % saham dengan score positif (market health)
    avg_composite_score: float      # Rata-rata score semua saham
    generated_at: datetime


# ─── CHAT ─────────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    user_id: str = "default"
    message: str
    context: Optional[dict] = None

class ChatResponse(BaseModel):
    response: str
    sources: List[str] = []
    timestamp: datetime
