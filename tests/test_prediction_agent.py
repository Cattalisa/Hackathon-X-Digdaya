"""
CHUNK 2 - Unit Tests: QuantPredictionAgent
Tests for all technical indicators and composite scoring logic.
"""
import pytest
import numpy as np
import pandas as pd
from datetime import datetime
from unittest.mock import patch, MagicMock
from backend.agents.prediction_agent import QuantPredictionAgent, _sanitize_float, FACTOR_WEIGHTS
from backend.models.schemas import Signal


class TestSanitizeFloat:
    """Tests for the _sanitize_float helper."""
    def test_normal_float(self):
        assert _sanitize_float(3.14) == 3.14

    def test_nan_returns_default(self):
        assert _sanitize_float(float('nan')) == 0.0

    def test_inf_returns_default(self):
        assert _sanitize_float(float('inf')) == 0.0
        assert _sanitize_float(float('-inf')) == 0.0

    def test_custom_default(self):
        assert _sanitize_float(float('nan'), default=50.0) == 50.0

    def test_none_returns_default(self):
        assert _sanitize_float(None) == 0.0

    def test_string_returns_default(self):
        assert _sanitize_float("not_a_float") == 0.0


class TestQuantPredictionAgent:
    @pytest.fixture
    def agent(self, mock_data_service):
        """Create agent with mocked DataService."""
        with patch("backend.agents.prediction_agent.DataService") as MockDS:
            MockDS.return_value = mock_data_service
            agent = QuantPredictionAgent()
            agent.data_service = mock_data_service
            return agent

    def test_rsi_neutral_on_short_data(self, agent, short_ohlcv):
        """RSI returns 50 (neutral) when data is too short for the period."""
        prices = short_ohlcv["Close"]
        # period=16 requires 17 rows, short_ohlcv has 15 -> returns 50.0
        rsi = agent._compute_rsi(prices, period=16)
        assert rsi == 50.0

    def test_rsi_range(self, agent, sample_ohlcv):
        """RSI always in [0, 100]."""
        prices = sample_ohlcv["Close"]
        rsi = agent._compute_rsi(prices)
        assert 0 <= rsi <= 100

    def test_macd_zeros_on_short_data(self, agent, short_ohlcv):
        """MACD returns (0, 0, 0) when data is too short."""
        prices = short_ohlcv["Close"]
        macd, sig, hist = agent._compute_macd(prices)
        assert macd == 0.0
        assert sig == 0.0
        assert hist == 0.0

    def test_macd_returns_finite(self, agent, sample_ohlcv):
        """MACD values are finite floats."""
        prices = sample_ohlcv["Close"]
        macd, sig, hist = agent._compute_macd(prices)
        assert np.isfinite(macd)
        assert np.isfinite(sig)
        assert np.isfinite(hist)

    def test_bollinger_fallback_on_short(self, agent, short_ohlcv):
        """Bollinger returns mid-price with ~5% bands on short data."""
        prices = short_ohlcv["Close"]
        upper, lower, pos = agent._compute_bollinger(prices, period=20)
        assert upper > lower
        assert 0 <= pos <= 1

    def test_bollinger_position_in_range(self, agent, sample_ohlcv):
        """Bollinger position always in [0, 1] for normal data."""
        prices = sample_ohlcv["Close"]
        upper, lower, pos = agent._compute_bollinger(prices)
        assert 0 <= pos <= 1

    def test_atr_positive(self, agent, sample_ohlcv):
        """ATR is always positive."""
        atr = agent._compute_atr(sample_ohlcv)
        assert atr > 0

    def test_atr_fallback_on_short(self, agent, short_ohlcv):
        """ATR uses daily range fallback on short data."""
        atr = agent._compute_atr(short_ohlcv, period=14)
        assert atr > 0

    def test_technical_factors_complete(self, agent, sample_ohlcv):
        """TechnicalFactors has all required fields."""
        tf = agent._compute_technical_factors(sample_ohlcv)
        assert -1.0 <= tf.factor_score <= 1.0
        assert 0 <= tf.rsi <= 100
        assert tf.rsi_signal in ("oversold", "mildly_oversold", "neutral", "mildly_overbought", "overbought")
        assert tf.macd_crossover in ("bullish_cross", "bearish_cross", "none")
        assert tf.bb_signal in ("near_lower", "middle", "near_upper")
        assert tf.ma_trend in ("above_both", "above_ma20_only", "below_ma20_only", "below_both")

    def test_momentum_factors_complete(self, agent, sample_ohlcv):
        """MomentumFactors has all required fields."""
        mf = agent._compute_momentum_factors(sample_ohlcv)
        assert -1.0 <= mf.factor_score <= 1.0
        assert mf.momentum_5_20 in ("bullish", "bearish", "neutral")
        assert mf.mean_reversion_signal in ("oversold", "mildly_oversold", "neutral", "mildly_overbought", "overbought")

    def test_volume_factors_complete(self, agent, sample_ohlcv):
        """VolumeFactors has all required fields."""
        vf = agent._compute_volume_factors(sample_ohlcv)
        assert -1.0 <= vf.factor_score <= 1.0
        assert vf.volume_trend in ("surge", "above_avg", "normal", "dry")
        assert vf.obv_trend in ("up", "flat", "down")

    def test_score_to_signal_thresholds(self, agent):
        """Score-to-signal conversion matches defined thresholds."""
        assert agent._score_to_signal(0.6) == Signal.STRONG_BUY
        assert agent._score_to_signal(0.3) == Signal.BUY
        assert agent._score_to_signal(0.0) == Signal.HOLD
        assert agent._score_to_signal(-0.3) == Signal.SELL
        assert agent._score_to_signal(-0.6) == Signal.STRONG_SELL

    def test_analyze_symbol_full(self, agent, sample_market_data, sample_sentiment, sample_ohlcv):
        """analyze_symbol returns valid QuantSignal for valid data."""
        agent.data_service.get_historical_data.return_value = sample_ohlcv
        result = agent.analyze_symbol(sample_market_data, sample_sentiment)
        assert result is not None
        assert result.symbol == "BBCA.JK"
        assert -1.0 <= result.composite_score <= 1.0
        assert result.signal in Signal
        assert result.target_price > 0
        assert result.stop_loss > 0
        assert len(result.key_risks) > 0

    def test_analyze_symbol_zero_price(self, agent, sample_market_data):
        """analyze_symbol returns None for zero-price stocks."""
        sample_market_data.price = 0.0
        result = agent.analyze_symbol(sample_market_data)
        assert result is None

    def test_analyze_symbol_insufficient_hist(self, agent, sample_market_data, short_ohlcv):
        """analyze_symbol returns None when hist < 20 rows."""
        agent.data_service.get_historical_data.return_value = short_ohlcv
        result = agent.analyze_symbol(sample_market_data)
        assert result is None

    def test_factor_weights_sum_to_one(self):
        """Factor weights must sum to 1.0."""
        total = sum(FACTOR_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9

    def test_price_targets_bullish(self, agent):
        """Bullish signals produce target > price and stop < price."""
        target, stop, rr, up, down = agent._compute_price_targets(6000.0, 100.0, Signal.BUY)
        assert target > 6000.0
        assert stop < 6000.0
        assert rr > 0
        assert up > 0
        assert down < 0

    def test_price_targets_bearish(self, agent):
        """Bearish signals produce target < price and stop > price."""
        target, stop, rr, up, down = agent._compute_price_targets(6000.0, 100.0, Signal.SELL)
        assert target < 6000.0
        assert stop > 6000.0
        assert rr > 0
