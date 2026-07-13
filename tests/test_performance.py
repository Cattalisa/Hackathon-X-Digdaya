"""
CHUNK 4 - Performance Tests: Benchmark key operations
Uses time-based assertions to ensure responses are within SLA.
"""
import pytest
import time
import numpy as np
import pandas as pd
from unittest.mock import MagicMock, patch


class TestIndicatorPerformance:
    """Benchmark individual indicator computations."""

    @pytest.fixture
    def agent(self, sample_ohlcv, sample_market_data):
        from backend.agents.prediction_agent import QuantPredictionAgent
        from backend.services.data_service import DataService
        with patch.object(DataService, "__init__", return_value=None):
            a = QuantPredictionAgent.__new__(QuantPredictionAgent)
            a.data_service = MagicMock()
            a.data_service.get_historical_data.return_value = sample_ohlcv
            return a

    def test_rsi_computation_speed(self, agent, sample_ohlcv):
        """RSI avg per-call latency < 5ms (100 iterations total < 500ms)."""
        prices = sample_ohlcv["Close"]
        start = time.perf_counter()
        for _ in range(100):
            agent._compute_rsi(prices)
        elapsed_ms = (time.perf_counter() - start) * 1000
        per_call_ms = elapsed_ms / 100
        assert per_call_ms < 5.0, f"RSI avg {per_call_ms:.2f}ms/call (>5ms)"

    def test_macd_computation_speed(self, agent, sample_ohlcv):
        """MACD avg per-call latency < 5ms (100 iterations total < 500ms)."""
        prices = sample_ohlcv["Close"]
        start = time.perf_counter()
        for _ in range(100):
            agent._compute_macd(prices)
        elapsed_ms = (time.perf_counter() - start) * 1000
        per_call_ms = elapsed_ms / 100
        assert per_call_ms < 5.0, f"MACD avg {per_call_ms:.2f}ms/call (>5ms)"

    def test_full_technical_factors_speed(self, agent, sample_ohlcv):
        """Full TechnicalFactors avg per-call < 20ms (50 iterations total < 1000ms)."""
        start = time.perf_counter()
        for _ in range(50):
            agent._compute_technical_factors(sample_ohlcv)
        elapsed_ms = (time.perf_counter() - start) * 1000
        per_call_ms = elapsed_ms / 50
        assert per_call_ms < 20.0, f"TechnicalFactors avg {per_call_ms:.2f}ms/call (>20ms)"

    def test_full_analyze_symbol_speed(self, agent, sample_market_data, sample_ohlcv):
        """Full analyze_symbol single call < 300ms."""
        agent.data_service.get_historical_data.return_value = sample_ohlcv
        start = time.perf_counter()
        result = agent.analyze_symbol(sample_market_data)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert result is not None
        assert elapsed_ms < 300, f"analyze_symbol took {elapsed_ms:.1f}ms (>300ms)"

    def test_rsi_correctness_uptrend(self, agent):
        """RSI > 50 on monotonically increasing price series."""
        prices = pd.Series(list(range(1000, 1100)), dtype=float)
        rsi = agent._compute_rsi(prices)
        assert rsi > 50, f"Expected RSI > 50 on uptrend, got {rsi:.1f}"

    def test_rsi_correctness_downtrend(self, agent):
        """RSI < 50 on monotonically decreasing price series."""
        prices = pd.Series(list(range(1100, 1000, -1)), dtype=float)
        rsi = agent._compute_rsi(prices)
        assert rsi < 50, f"Expected RSI < 50 on downtrend, got {rsi:.1f}"

    def test_bollinger_width_proportional_to_volatility(self, agent):
        """Higher volatility series has wider Bollinger Bands."""
        rng = np.random.default_rng(42)
        low_vol = pd.Series(5000 + rng.normal(0, 10, 30))
        high_vol = pd.Series(5000 + rng.normal(0, 200, 30))
        
        u1, l1, _ = agent._compute_bollinger(low_vol)
        u2, l2, _ = agent._compute_bollinger(high_vol)
        
        width_low = u1 - l1
        width_high = u2 - l2
        assert width_high > width_low, "High-vol series should have wider bands"


class TestDataServicePerformance:
    """Performance tests for DataService batch operations."""

    def test_batch_10_symbols_timing(self):
        """Batch fetch 10 symbols (SQLite fallback) < 15s."""
        from backend.services.data_service import DataService
        ds = DataService()
        ds._session = MagicMock()
        ds._session.get.side_effect = ConnectionError("No Deno")
        
        symbols = ["BBCA.JK", "BBRI.JK", "BMRI.JK", "TLKM.JK", "ASII.JK",
                   "GOTO.JK", "UNVR.JK", "ANTM.JK", "INDF.JK", "KLBF.JK"]
        
        start = time.time()
        results = ds.get_market_data(symbols)
        elapsed = time.time() - start
        
        assert len(results) == 10
        assert elapsed < 15.0, f"10-symbol SQLite fetch took {elapsed:.1f}s (>15s)"

    def test_cache_hit_speed(self):
        """Cached call is faster than uncached call."""
        from backend.services.data_service import DataService
        ds = DataService()
        ds._session = MagicMock()
        ds._session.get.side_effect = ConnectionError("No Deno")
        
        # Warm up the cache
        ds.get_market_data(["BBCA.JK"])
        
        # Measure cached call
        start = time.perf_counter()
        ds.get_market_data(["BBCA.JK"])
        cached_ms = (time.perf_counter() - start) * 1000
        
        # Cached call should be very fast (< 5ms)
        assert cached_ms < 5.0, f"Cached call took {cached_ms:.2f}ms (>5ms)"
