"""
NusaTerminal - Quant Analysis Engine
Multi-Factor Scoring Model terinspirasi dari pendekatan kuantitatif institusional.

Faktor yang digunakan:
  1. Technical Analysis  (RSI, MACD, Bollinger Bands, Moving Average) → 30%
  2. Momentum            (return 5/20/60 hari, z-score mean reversion)  → 25%
  3. Sentiment AI        (IndoBERT score dari berita)                    → 25%
  4. Volume Anomaly      (volume ratio, OBV trend)                       → 20%

Output:
  - Composite Score (-1 sampai +1)
  - Signal (STRONG_BUY / BUY / HOLD / SELL / STRONG_SELL)
  - Target Price (ATR-based, risk:reward ~1:2)
  - Stop Loss (ATR-based)
  - Factor Breakdown (transparansi penuh per faktor)

⚠️  Disclaimer: Ini adalah alat analisis edukatif, bukan nasihat investasi.
"""

import numpy as np
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import logging

from ..models.schemas import (
    MarketData, SentimentAnalysis, QuantSignal, QuantDashboard,
    Signal, TechnicalFactors, MomentumFactors, VolumeFactors, Sentiment
)
from ..services.data_service import DataService

logger = logging.getLogger(__name__)


def _sanitize_float(v, default: float = 0.0) -> float:
    """Ganti NaN/Inf dengan default agar JSON serializable."""
    try:
        f = float(v)
        if f != f or f == float('inf') or f == float('-inf'):  # NaN or Inf check
            return default
        return f
    except (TypeError, ValueError):
        return default


def _sanitize_dict(d: dict) -> dict:
    """Rekursif sanitasi semua float dalam dict."""
    result = {}
    for k, v in d.items():
        if isinstance(v, dict):
            result[k] = _sanitize_dict(v)
        elif isinstance(v, float):
            result[k] = _sanitize_float(v)
        else:
            result[k] = v
    return result


# ─── KONSTANTA ────────────────────────────────────────────────────────────────

FACTOR_WEIGHTS = {
    "technical":  0.30,
    "momentum":   0.25,
    "sentiment":  0.25,
    "volume":     0.20,
}

# Signal threshold dari composite score
SIGNAL_THRESHOLDS = {
    Signal.STRONG_BUY:  0.5,
    Signal.BUY:         0.2,
    Signal.HOLD:        -0.2,
    Signal.SELL:        -0.5,
    Signal.STRONG_SELL: -1.0,   # < -0.5
}

# ATR multiplier untuk target & stop loss
ATR_TARGET_MULTIPLIER = 2.0     # Target = price + (ATR * 2)
ATR_STOPLOSS_MULTIPLIER = 1.0   # Stop = price - (ATR * 1) → Risk:Reward = 1:2


# ─── QUANT ENGINE ─────────────────────────────────────────────────────────────

class QuantPredictionAgent:
    """
    Multi-factor quant scoring engine untuk saham IDX Indonesia.
    Setiap faktor menghasilkan score -1 sampai +1, lalu digabung
    dengan weighted average menjadi composite score.
    """

    def __init__(self):
        self.data_service = DataService()

    # ══════════════════════════════════════════════════════════════════════════
    # FACTOR 1: TECHNICAL ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════

    def _compute_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """Hitung RSI (Relative Strength Index)."""
        if len(prices) < period + 1:
            return 50.0  # Neutral jika data tidak cukup

        delta = prices.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.rolling(window=period, min_periods=period).mean().iloc[-1]
        avg_loss = loss.rolling(window=period, min_periods=period).mean().iloc[-1]

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        result = 100 - (100 / (1 + rs))
        return _sanitize_float(result, 50.0)

    def _compute_macd(
        self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> Tuple[float, float, float]:
        """Hitung MACD, Signal line, dan Histogram."""
        if len(prices) < slow + signal:
            return 0.0, 0.0, 0.0

        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line

        return (
            _sanitize_float(round(macd_line.iloc[-1], 4)),
            _sanitize_float(round(signal_line.iloc[-1], 4)),
            _sanitize_float(round(histogram.iloc[-1], 4))
        )

    def _compute_bollinger(
        self, prices: pd.Series, period: int = 20, num_std: float = 2.0
    ) -> Tuple[float, float, float]:
        """
        Hitung Bollinger Bands.
        Returns: (upper, lower, position) dimana position 0=lower, 0.5=mid, 1=upper
        """
        if len(prices) < period:
            mid = prices.iloc[-1]
            return mid * 1.05, mid * 0.95, 0.5

        sma = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()

        upper = sma + (std * num_std)
        lower = sma - (std * num_std)

        upper_val = upper.iloc[-1]
        lower_val = lower.iloc[-1]
        current = prices.iloc[-1]

        band_width = upper_val - lower_val
        position = (current - lower_val) / band_width if band_width > 0 else 0.5

        return round(upper_val, 2), round(lower_val, 2), round(position, 4)

    def _compute_technical_factors(self, hist: pd.DataFrame) -> TechnicalFactors:
        """
        Hitung semua indikator teknikal dan agregasikan jadi satu factor_score.
        
        Scoring logic:
        - RSI < 30 → oversold → bullish (+)
        - RSI > 70 → overbought → bearish (-)
        - MACD histogram positif & naik → bullish (+)
        - Harga di bawah BB lower → potensi rebound (+)
        - Harga di atas MA20 & MA50 → trend up (+)
        """
        prices = hist["Close"]

        # RSI
        rsi = self._compute_rsi(prices)
        if rsi < 30:
            rsi_score = 0.8      # Sangat oversold → bullish
            rsi_signal = "oversold"
        elif rsi < 45:
            rsi_score = 0.3
            rsi_signal = "mildly_oversold"
        elif rsi < 55:
            rsi_score = 0.0
            rsi_signal = "neutral"
        elif rsi < 70:
            rsi_score = -0.3
            rsi_signal = "mildly_overbought"
        else:
            rsi_score = -0.8     # Sangat overbought → bearish
            rsi_signal = "overbought"

        # MACD
        macd, macd_sig, macd_hist = self._compute_macd(prices)
        if macd_hist > 0 and macd > macd_sig:
            macd_score = min(macd_hist / (abs(macd) + 1e-9), 1.0)
            macd_crossover = "bullish_cross"
        elif macd_hist < 0 and macd < macd_sig:
            macd_score = max(macd_hist / (abs(macd) + 1e-9), -1.0)
            macd_crossover = "bearish_cross"
        else:
            macd_score = 0.0
            macd_crossover = "none"
        macd_score = float(np.clip(macd_score, -1, 1))

        # Bollinger Bands
        bb_upper, bb_lower, bb_pos = self._compute_bollinger(prices)
        if bb_pos < 0.2:
            bb_score = 0.7       # Near lower band → potensi rebound
            bb_signal = "near_lower"
        elif bb_pos > 0.8:
            bb_score = -0.5      # Near upper band → potensi pullback
            bb_signal = "near_upper"
        else:
            bb_score = 0.0
            bb_signal = "middle"

        # Moving Averages
        current = prices.iloc[-1]
        ma_20 = prices.rolling(20).mean().iloc[-1] if len(prices) >= 20 else current
        ma_50 = prices.rolling(50).mean().iloc[-1] if len(prices) >= 50 else current

        if current > ma_20 and current > ma_50:
            ma_score = 0.6
            ma_trend = "above_both"
        elif current > ma_20 and current < ma_50:
            ma_score = 0.2
            ma_trend = "above_ma20_only"
        elif current < ma_20 and current > ma_50:
            ma_score = -0.2
            ma_trend = "below_ma20_only"
        else:
            ma_score = -0.6
            ma_trend = "below_both"

        # Weighted agregat technical factors
        factor_score = (
            rsi_score   * 0.35 +
            macd_score  * 0.30 +
            bb_score    * 0.20 +
            ma_score    * 0.15
        )

        return TechnicalFactors(
            rsi=_sanitize_float(round(rsi, 2), 50.0),
            rsi_signal=rsi_signal,
            macd=_sanitize_float(macd),
            macd_signal=_sanitize_float(macd_sig),
            macd_histogram=_sanitize_float(macd_hist),
            macd_crossover=macd_crossover,
            bb_upper=_sanitize_float(bb_upper),
            bb_lower=_sanitize_float(bb_lower),
            bb_position=_sanitize_float(bb_pos, 0.5),
            bb_signal=bb_signal,
            ma_20=_sanitize_float(round(ma_20, 2)),
            ma_50=_sanitize_float(round(ma_50, 2)),
            ma_trend=ma_trend,
            factor_score=_sanitize_float(round(float(np.clip(factor_score, -1, 1)), 4))
        )

    # ══════════════════════════════════════════════════════════════════════════
    # FACTOR 2: MOMENTUM & MEAN REVERSION
    # ══════════════════════════════════════════════════════════════════════════

    def _compute_momentum_factors(self, hist: pd.DataFrame) -> MomentumFactors:
        """
        Kalkulasi momentum return (5/20/60 hari) dan z-score untuk mean reversion.
        
        Scoring:
        - Return 5d > 0 dan > return 20d → short-term momentum positif
        - Z-score < -1.5 → harga jauh di bawah rata-rata → mean reversion bullish
        """
        prices = hist["Close"]
        current = prices.iloc[-1]

        def safe_return(n: int) -> float:
            if len(prices) > n:
                return ((current / prices.iloc[-n - 1]) - 1) * 100
            return 0.0

        ret_5d  = safe_return(5)
        ret_20d = safe_return(20)
        ret_60d = safe_return(60)

        # Momentum score: bandingkan return jangka pendek vs menengah
        if ret_5d > 0 and ret_5d > ret_20d * 0.5:
            momentum_score = min(ret_5d / 5, 1.0)   # Cap di +1
            momentum_signal = "bullish"
        elif ret_5d < 0 and ret_5d < ret_20d * 0.5:
            momentum_score = max(ret_5d / 5, -1.0)  # Cap di -1
            momentum_signal = "bearish"
        else:
            momentum_score = 0.0
            momentum_signal = "neutral"

        # Z-score untuk mean reversion (harga vs MA20)
        if len(prices) >= 20:
            ma = prices.rolling(20).mean()
            std = prices.rolling(20).std()
            z = (current - ma.iloc[-1]) / (std.iloc[-1] + 1e-9)
        else:
            z = 0.0

        # Mean reversion: z-score ekstrem → antisipasi pembalikan
        if z < -1.5:
            mr_score = 0.6       # Sangat di bawah rata-rata → rebound
            mr_signal = "oversold"
        elif z < -0.5:
            mr_score = 0.2
            mr_signal = "mildly_oversold"
        elif z > 1.5:
            mr_score = -0.6      # Sangat di atas rata-rata → pullback
            mr_signal = "overbought"
        elif z > 0.5:
            mr_score = -0.2
            mr_signal = "mildly_overbought"
        else:
            mr_score = 0.0
            mr_signal = "neutral"

        # Gabungkan momentum + mean reversion
        factor_score = momentum_score * 0.6 + mr_score * 0.4

        return MomentumFactors(
            return_5d=_sanitize_float(round(ret_5d, 4)),
            return_20d=_sanitize_float(round(ret_20d, 4)),
            return_60d=_sanitize_float(round(ret_60d, 4)),
            momentum_5_20=momentum_signal,
            z_score=_sanitize_float(round(float(z), 4)),
            mean_reversion_signal=mr_signal,
            factor_score=_sanitize_float(round(float(np.clip(factor_score, -1, 1)), 4))
        )

    # ══════════════════════════════════════════════════════════════════════════
    # FACTOR 3: VOLUME ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════

    def _compute_volume_factors(self, hist: pd.DataFrame) -> VolumeFactors:
        """
        Deteksi anomali volume dan hitung On-Balance Volume (OBV).
        
        Volume surge + harga naik → konfirmasi bullish
        Volume surge + harga turun → konfirmasi bearish
        Volume rendah → sinyal lemah
        """
        prices = hist["Close"]
        volumes = hist["Volume"]

        avg_vol_20d = volumes.rolling(20).mean().iloc[-1] if len(volumes) >= 20 else volumes.mean()
        current_vol = volumes.iloc[-1]
        current_price = prices.iloc[-1]
        prev_price = prices.iloc[-2] if len(prices) > 1 else current_price

        volume_ratio = current_vol / (avg_vol_20d + 1e-9)

        # Volume classification
        if volume_ratio > 2.0:
            vol_trend = "surge"
        elif volume_ratio > 1.3:
            vol_trend = "above_avg"
        elif volume_ratio < 0.5:
            vol_trend = "dry"
        else:
            vol_trend = "normal"

        # Volume score: surge + harga naik → bullish confirmation
        price_direction = 1 if current_price >= prev_price else -1
        if volume_ratio > 1.5:
            vol_score = price_direction * min(volume_ratio / 2, 1.0)
        elif volume_ratio < 0.5:
            vol_score = 0.0  # Volume kering → sinyal tidak valid
        else:
            vol_score = price_direction * 0.2

        # On-Balance Volume (OBV) trend
        if len(hist) >= 5:
            obv = pd.Series(0.0, index=hist.index)
            for i in range(1, len(hist)):
                if hist["Close"].iloc[i] > hist["Close"].iloc[i - 1]:
                    obv.iloc[i] = obv.iloc[i - 1] + hist["Volume"].iloc[i]
                elif hist["Close"].iloc[i] < hist["Close"].iloc[i - 1]:
                    obv.iloc[i] = obv.iloc[i - 1] - hist["Volume"].iloc[i]
                else:
                    obv.iloc[i] = obv.iloc[i - 1]

            obv_5d_change = obv.iloc[-1] - obv.iloc[-5]
            if obv_5d_change > 0:
                obv_trend = "up"
                vol_score = min(vol_score + 0.1, 1.0)
            elif obv_5d_change < 0:
                obv_trend = "down"
                vol_score = max(vol_score - 0.1, -1.0)
            else:
                obv_trend = "flat"
        else:
            obv_trend = "flat"

        return VolumeFactors(
            avg_volume_20d=_sanitize_float(round(float(avg_vol_20d), 0)),
            volume_ratio=_sanitize_float(round(float(volume_ratio), 4)),
            volume_trend=vol_trend,
            obv_trend=obv_trend,
            factor_score=_sanitize_float(round(float(np.clip(vol_score, -1, 1)), 4))
        )

    # ══════════════════════════════════════════════════════════════════════════
    # ATR-BASED TARGET PRICE & STOP LOSS
    # ══════════════════════════════════════════════════════════════════════════

    def _compute_atr(self, hist: pd.DataFrame, period: int = 14) -> float:
        """
        Hitung Average True Range (ATR) — ukuran volatilitas standar quant.
        True Range = max(High-Low, |High-PrevClose|, |Low-PrevClose|)
        """
        if len(hist) < period + 1:
            # Fallback: gunakan rata-rata daily range
            return float((hist["High"] - hist["Low"]).mean())

        high = hist["High"]
        low  = hist["Low"]
        close_prev = hist["Close"].shift(1)

        tr = pd.concat([
            high - low,
            (high - close_prev).abs(),
            (low  - close_prev).abs()
        ], axis=1).max(axis=1)

        atr = tr.rolling(window=period).mean().iloc[-1]
        return _sanitize_float(round(float(atr), 4), default=float((hist["High"] - hist["Low"]).mean()))

    def _compute_price_targets(
        self,
        current_price: float,
        atr: float,
        signal: Signal
    ) -> Tuple[float, float, float, float]:
        """
        Hitung target price dan stop loss berbasis ATR.
        
        Untuk BUY signal:
          - Target  = price + (ATR × 2.0)  → potensi profit 2×ATR
          - Stop    = price - (ATR × 1.0)  → risiko 1×ATR
          - R:R     = 2:1

        Untuk SELL signal (short perspective):
          - Target  = price - (ATR × 2.0)
          - Stop    = price + (ATR × 1.0)
          
        Returns: (target_price, stop_loss, risk_reward_ratio, upside_pct, downside_pct)
        """
        is_bullish = signal in [Signal.STRONG_BUY, Signal.BUY, Signal.HOLD]

        if is_bullish:
            target    = current_price + (atr * ATR_TARGET_MULTIPLIER)
            stop_loss = current_price - (atr * ATR_STOPLOSS_MULTIPLIER)
        else:
            target    = current_price - (atr * ATR_TARGET_MULTIPLIER)
            stop_loss = current_price + (atr * ATR_STOPLOSS_MULTIPLIER)

        potential_gain = abs(target - current_price)
        potential_loss = abs(stop_loss - current_price)
        rr = potential_gain / (potential_loss + 1e-9)

        upside_pct   = ((target - current_price) / current_price) * 100
        downside_pct = ((stop_loss - current_price) / current_price) * 100

        return (
            round(target, 2),
            round(stop_loss, 2),
            round(rr, 2),
            round(upside_pct, 2),
            round(downside_pct, 2)
        )

    # ══════════════════════════════════════════════════════════════════════════
    # COMPOSITE SCORING & SIGNAL GENERATION
    # ══════════════════════════════════════════════════════════════════════════

    def _score_to_signal(self, score: float) -> Signal:
        """Convert composite score ke Signal enum."""
        if score >= 0.5:
            return Signal.STRONG_BUY
        elif score >= 0.2:
            return Signal.BUY
        elif score >= -0.2:
            return Signal.HOLD
        elif score >= -0.5:
            return Signal.SELL
        else:
            return Signal.STRONG_SELL

    def _build_reasoning(
        self,
        signal: Signal,
        technical: TechnicalFactors,
        momentum: MomentumFactors,
        volume: VolumeFactors,
        sentiment_score: float,
        composite_score: float
    ) -> Tuple[str, List[str]]:
        """Buat narasi reasoning dan daftar risiko."""
        signal_label = signal.value.replace("_", " ").title()

        # Kumpulkan highlight positif dan negatif
        positives = []
        negatives = []
        risks = []

        # Technical
        if technical.rsi_signal == "oversold":
            positives.append(f"RSI {technical.rsi:.0f} (oversold)")
        elif technical.rsi_signal == "overbought":
            negatives.append(f"RSI {technical.rsi:.0f} (overbought)")

        if technical.macd_crossover == "bullish_cross":
            positives.append("MACD bullish crossover")
        elif technical.macd_crossover == "bearish_cross":
            negatives.append("MACD bearish crossover")

        if technical.ma_trend == "above_both":
            positives.append("harga di atas MA20 & MA50")
        elif technical.ma_trend == "below_both":
            negatives.append("harga di bawah MA20 & MA50")

        # Momentum
        if momentum.return_5d > 2:
            positives.append(f"momentum 5 hari +{momentum.return_5d:.1f}%")
        elif momentum.return_5d < -2:
            negatives.append(f"momentum 5 hari {momentum.return_5d:.1f}%")

        if momentum.mean_reversion_signal == "oversold":
            positives.append(f"z-score {momentum.z_score:.1f} (potensi rebound)")
        elif momentum.mean_reversion_signal == "overbought":
            negatives.append(f"z-score {momentum.z_score:.1f} (risiko pullback)")

        # Volume
        if volume.volume_trend == "surge":
            vol_ctx = "bullish" if volume.factor_score > 0 else "bearish"
            (positives if vol_ctx == "bullish" else negatives).append(
                f"volume surge {volume.volume_ratio:.1f}× rata-rata ({vol_ctx})"
            )

        # Sentiment
        if sentiment_score > 0.3:
            positives.append(f"sentimen berita positif ({sentiment_score:+.2f})")
        elif sentiment_score < -0.3:
            negatives.append(f"sentimen berita negatif ({sentiment_score:+.2f})")

        # Build reasoning text
        parts = [f"Sinyal {signal_label} (score: {composite_score:+.2f})."]
        if positives:
            parts.append("Faktor bullish: " + ", ".join(positives) + ".")
        if negatives:
            parts.append("Faktor bearish: " + ", ".join(negatives) + ".")

        # Risks
        if technical.bb_position > 0.8:
            risks.append("Harga mendekati Bollinger Band atas — risiko pullback")
        if volume.volume_trend == "dry":
            risks.append("Volume rendah — sinyal kurang terkonfirmasi")
        if abs(momentum.z_score) > 2:
            risks.append("Harga terlalu jauh dari rata-rata — waspadai reversal")
        if abs(composite_score) < 0.3:
            risks.append("Sinyal lemah — pertimbangkan menunggu konfirmasi lebih lanjut")
        if not risks:
            risks.append("Selalu pasang stop loss sesuai toleransi risiko Anda")

        return " ".join(parts), risks

    # ══════════════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ══════════════════════════════════════════════════════════════════════════

    def analyze_symbol(
        self,
        market_data: MarketData,
        sentiment: Optional[SentimentAnalysis] = None,
        hist_period: str = "3mo"
    ) -> Optional[QuantSignal]:
        """
        Analisis kuantitatif lengkap untuk satu simbol saham.
        
        Args:
            market_data: Data harga real-time dari MarketAgent
            sentiment: Hasil IndoBERT sentiment (opsional)
            hist_period: Periode data historis ("1mo", "3mo", "6mo", "1y")
            
        Returns:
            QuantSignal dengan composite score, target, stop loss, dan breakdown
        """
        if market_data.price <= 0:
            return None

        # Ambil data historis untuk kalkulasi indikator
        hist = self.data_service.get_historical_data(market_data.symbol, hist_period)
        if hist.empty or len(hist) < 20:
            logger.warning(f"Data historis tidak cukup untuk {market_data.symbol}")
            return None

        # ── Kalkulasi semua faktor ────────────────────────────────────────────
        technical = self._compute_technical_factors(hist)
        momentum  = self._compute_momentum_factors(hist)
        volume    = self._compute_volume_factors(hist)

        # Sentiment score dari IndoBERT (-1 sampai +1)
        if sentiment:
            sentiment_score = float(sentiment.score)
            sentiment_label = sentiment.sentiment.value
        else:
            sentiment_score = 0.0
            sentiment_label = "neutral"

        # ── Composite Score (weighted average) ────────────────────────────────
        composite_score = (
            technical.factor_score  * FACTOR_WEIGHTS["technical"] +
            momentum.factor_score   * FACTOR_WEIGHTS["momentum"]  +
            sentiment_score         * FACTOR_WEIGHTS["sentiment"]  +
            volume.factor_score     * FACTOR_WEIGHTS["volume"]
        )
        composite_score = _sanitize_float(float(np.clip(composite_score, -1, 1)))

        # ── Signal dari composite score ───────────────────────────────────────
        signal = self._score_to_signal(composite_score)

        # Confidence = |composite_score| (semakin ekstrem, semakin yakin)
        confidence = min(abs(composite_score) * 1.5, 1.0)

        # ── ATR & Price Targets ───────────────────────────────────────────────
        atr = self._compute_atr(hist)
        target, stop_loss, rr, upside_pct, downside_pct = self._compute_price_targets(
            market_data.price, atr, signal
        )

        # ── Factor Contributions (untuk transparansi) ─────────────────────────
        factor_contributions = {
            "technical":  _sanitize_float(round(technical.factor_score  * FACTOR_WEIGHTS["technical"],  4)),
            "momentum":   _sanitize_float(round(momentum.factor_score   * FACTOR_WEIGHTS["momentum"],   4)),
            "sentiment":  _sanitize_float(round(sentiment_score         * FACTOR_WEIGHTS["sentiment"],  4)),
            "volume":     _sanitize_float(round(volume.factor_score     * FACTOR_WEIGHTS["volume"],     4)),
        }

        # ── Narasi & Risiko ───────────────────────────────────────────────────
        reasoning, key_risks = self._build_reasoning(
            signal, technical, momentum, volume, sentiment_score, composite_score
        )

        return QuantSignal(
            symbol=market_data.symbol,
            name=market_data.name,
            current_price=_sanitize_float(market_data.price),
            composite_score=_sanitize_float(round(composite_score, 4)),
            signal=signal,
            confidence=_sanitize_float(round(confidence, 4)),
            technical=technical,
            momentum=momentum,
            volume=volume,
            sentiment_score=_sanitize_float(round(sentiment_score, 4)),
            sentiment_label=sentiment_label,
            factor_weights=FACTOR_WEIGHTS,
            factor_contributions=factor_contributions,
            atr=_sanitize_float(atr),
            target_price=_sanitize_float(target),
            stop_loss=_sanitize_float(stop_loss),
            risk_reward_ratio=_sanitize_float(rr),
            upside_pct=_sanitize_float(upside_pct),
            downside_pct=_sanitize_float(downside_pct),
            reasoning=reasoning,
            key_risks=key_risks,
            timeframe="3–5 hari trading",
            generated_at=datetime.now()
        )

    def generate_signals(
        self,
        market_data_list: List[MarketData],
        sentiment_data: List[SentimentAnalysis]
    ) -> List[QuantSignal]:
        """
        Generate sinyal quant untuk semua saham dalam watchlist.
        
        Args:
            market_data_list: Data real-time semua saham
            sentiment_data: Hasil IndoBERT per saham
            
        Returns:
            List QuantSignal, diurutkan dari composite_score tertinggi
        """
        sentiment_map = {s.symbol: s for s in sentiment_data}
        signals = []

        for market_data in market_data_list:
            if market_data.price <= 0:
                continue

            sentiment = sentiment_map.get(market_data.symbol)

            try:
                signal = self.analyze_symbol(market_data, sentiment)
                if signal:
                    signals.append(signal)
            except Exception as e:
                logger.error(f"Error analisis quant {market_data.symbol}: {e}")
                continue

        # Sort dari bullish terkuat ke bearish terkuat
        signals.sort(key=lambda x: x.composite_score, reverse=True)
        return signals

    def get_quant_dashboard(
        self,
        market_data_list: List[MarketData],
        sentiment_data: List[SentimentAnalysis]
    ) -> QuantDashboard:
        """
        Generate QuantDashboard — ringkasan semua sinyal untuk tampilan utama.
        """
        signals = self.generate_signals(market_data_list, sentiment_data)

        categorized = {
            "strong_buy":  [s for s in signals if s.signal == Signal.STRONG_BUY],
            "buy":         [s for s in signals if s.signal == Signal.BUY],
            "hold":        [s for s in signals if s.signal == Signal.HOLD],
            "sell":        [s for s in signals if s.signal == Signal.SELL],
            "strong_sell": [s for s in signals if s.signal == Signal.STRONG_SELL],
        }

        positive_count = len(categorized["strong_buy"]) + len(categorized["buy"])
        total = len(signals)
        market_breadth = (positive_count / total) if total > 0 else 0.5
        avg_score = sum(s.composite_score for s in signals) / total if total > 0 else 0.0

        return QuantDashboard(
            **categorized,
            market_breadth=round(market_breadth, 4),
            avg_composite_score=round(avg_score, 4),
            generated_at=datetime.now()
        )

    # Backward compat alias
    def get_signal_summary(self) -> Dict:
        """Legacy method untuk kompatibilitas dengan main.py lama."""
        market_data = self.data_service.get_market_data()
        signals = self.generate_signals(market_data, [])
        return {
            "total_signals": len(signals),
            "buy_signals": len([s for s in signals if s.signal in [Signal.BUY, Signal.STRONG_BUY]]),
            "sell_signals": len([s for s in signals if s.signal in [Signal.SELL, Signal.STRONG_SELL]]),
            "hold_signals": len([s for s in signals if s.signal == Signal.HOLD]),
            "top_signals": signals[:5],
            "timestamp": datetime.now()
        }
