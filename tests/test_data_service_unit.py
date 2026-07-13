"""
CHUNK 2 - Unit Tests: DataService
Tests for SQLite data retrieval, caching, and fallback logic.
"""
import pytest
import sqlite3
import pandas as pd
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime
from backend.services.data_service import DataService, DB_PATH


class TestDataServiceInit:
    def test_init_creates_caches(self):
        """DataService initializes with TTL caches."""
        ds = DataService()
        assert ds._realtime_cache is not None
        assert ds._summary_cache is not None
        assert ds._session is not None


class TestDataServiceSQLiteFallback:
    """Tests for SQLite fallback layer (Deno API mocked to fail)."""

    @pytest.fixture
    def ds_no_deno(self):
        """DataService with Deno API always failing."""
        ds = DataService()
        # Force session to raise ConnectionError
        ds._session = MagicMock()
        ds._session.get.side_effect = ConnectionError("Deno not running")
        return ds

    def test_get_all_symbols_returns_dict(self, ds_no_deno):
        """get_all_symbols() returns non-empty dict from SQLite."""
        symbols = ds_no_deno.get_all_symbols()
        assert isinstance(symbols, dict)
        assert len(symbols) > 0
        # All symbols should have .JK suffix
        for sym in list(symbols.keys())[:5]:
            assert sym.endswith(".JK"), f"Symbol {sym} should end with .JK"

    def test_get_market_data_bbca(self, ds_no_deno):
        """get_market_data() returns MarketData for BBCA.JK."""
        results = ds_no_deno.get_market_data(["BBCA.JK"])
        assert len(results) == 1
        md = results[0]
        assert md.symbol == "BBCA.JK"
        assert md.price >= 0

    def test_get_historical_data_returns_df(self, ds_no_deno):
        """get_historical_data() returns DataFrame with OHLCV columns."""
        df = ds_no_deno.get_historical_data("BBCA.JK", "3mo")
        if not df.empty:
            assert "Close" in df.columns
            assert "Open" in df.columns
            assert "High" in df.columns
            assert "Low" in df.columns
            assert "Volume" in df.columns

    def test_symbol_info_fallback(self, ds_no_deno):
        """get_symbol_info() returns dict even when Deno fails."""
        info = ds_no_deno.get_symbol_info("BBCA.JK")
        assert isinstance(info, dict)
        assert "symbol" in info

    def test_caching_works(self, ds_no_deno):
        """Second call uses cache, doesn't hit Deno again."""
        results1 = ds_no_deno.get_market_data(["BBCA.JK"])
        call_count_after_first = ds_no_deno._session.get.call_count

        results2 = ds_no_deno.get_market_data(["BBCA.JK"])
        # Cache should prevent new API calls
        assert ds_no_deno._session.get.call_count == call_count_after_first

    def test_fallback_returns_non_negative_price(self, ds_no_deno):
        """Fallback MarketData has non-negative price."""
        results = ds_no_deno.get_market_data(["BBCA.JK"])
        for r in results:
            assert r.price >= 0

    def test_unknown_symbol_returns_fallback(self, ds_no_deno):
        """Unknown symbol returns fallback with price=0."""
        results = ds_no_deno.get_market_data(["ZZZZZZZ.JK"])
        assert len(results) == 1
        assert results[0].price == 0.0


class TestDataServiceDeno:
    """Tests for Deno API primary layer (Deno mocked to succeed)."""

    @pytest.fixture
    def ds_with_deno(self):
        """DataService with mocked successful Deno API."""
        import json
        ds = DataService()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{
                "close": 6175.0,
                "previous": 6200.0,
                "change": -25.0,
                "volume": 138050500,
                "open": 6300.0,
                "high": 6300.0,
                "low": 6125.0,
            }]
        }
        ds._session = MagicMock()
        ds._session.get.return_value = mock_response
        return ds

    def test_deno_primary_fetch(self, ds_with_deno):
        """When Deno returns 200, data is used without SQLite."""
        results = ds_with_deno.get_market_data(["BBCA.JK"])
        assert len(results) == 1
        assert results[0].price == 6175.0
        assert results[0].change == -25.0


class TestDataServiceBatchFetch:
    def test_batch_fetch_multiple_symbols(self):
        """Batch fetch handles multiple symbols concurrently."""
        ds = DataService()
        ds._session = MagicMock()
        ds._session.get.side_effect = ConnectionError("No Deno")
        
        symbols = ["BBCA.JK", "BBRI.JK", "BMRI.JK"]
        results = ds.get_market_data(symbols)
        assert len(results) == 3  # All symbols should return something
