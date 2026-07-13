"""
NusaTerminal Test Suite - conftest.py
Shared fixtures and mocks for all tests.
"""
import sys
import os
import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def make_ohlcv_df(n: int = 90, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    base_price = 6000.0
    prices = base_price + np.cumsum(rng.normal(0, 50, n))
    prices = np.clip(prices, 1000, 20000)
    return pd.DataFrame({
        "Open":   prices * (1 - rng.uniform(0, 0.01, n)),
        "High":   prices * (1 + rng.uniform(0, 0.02, n)),
        "Low":    prices * (1 - rng.uniform(0, 0.02, n)),
        "Close":  prices,
        "Volume": rng.integers(1_000_000, 50_000_000, n),
    }, index=pd.date_range("2025-01-01", periods=n, freq="B"))


@pytest.fixture
def sample_ohlcv():
    return make_ohlcv_df(90)


@pytest.fixture
def short_ohlcv():
    return make_ohlcv_df(15)


@pytest.fixture
def sample_market_data():
    from backend.models.schemas import MarketData, MarketType
    return MarketData(
        symbol="BBCA.JK",
        name="PT Bank Central Asia Tbk.",
        price=6175.0,
        change=-25.0,
        change_percent=-0.40,
        volume=138_050_500,
        open=6300.0,
        high=6300.0,
        low=6125.0,
        close=6175.0,
        last_update=datetime.now(),
        market_type=MarketType.STOCK,
    )


@pytest.fixture
def sample_sentiment():
    from backend.models.schemas import SentimentAnalysis, Sentiment
    return SentimentAnalysis(
        symbol="BBCA.JK",
        sentiment=Sentiment.BULLISH,
        score=0.6,
        confidence=0.85,
        news_count=5,
        last_updated=datetime.now(),
    )


@pytest.fixture
def mock_data_service(sample_ohlcv, sample_market_data):
    svc = MagicMock()
    svc.get_historical_data.return_value = sample_ohlcv
    svc.get_market_data.return_value = [sample_market_data]
    svc.get_all_symbols.return_value = {"BBCA.JK": "Bank Central Asia"}
    return svc
