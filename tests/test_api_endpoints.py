"""
CHUNK 3 - FastAPI Endpoint Tests
Tests API endpoints using httpx TestClient (no external dependencies required).
"""
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def app_client():
    """Create FastAPI TestClient with all agents mocked."""
    # Mock all agents and services before importing main
    market_mock = MagicMock()
    sentiment_mock = MagicMock()
    sentiment_mock.model_name = "mdhugol/indonesia-bert-sentiment-classification"
    prediction_mock = MagicMock()
    chatbot_mock = MagicMock()
    chatbot_mock.get_stats.return_value = {
        "vector_store": {"news_count": 50, "market_count": 5},
        "llm_active": False,
        "llm_model": "none"
    }

    from backend.models.schemas import MarketData, MarketType, SentimentAnalysis, Sentiment, QuantDashboard, Signal
    sample_md = MarketData(
        symbol="BBCA.JK", name="Bank Central Asia",
        price=6175.0, change=-25.0, change_percent=-0.4,
        volume=138050500, open=6300.0, high=6300.0, low=6125.0, close=6175.0,
        last_update=datetime.now(), market_type=MarketType.STOCK
    )
    sample_sa = SentimentAnalysis(
        symbol="BBCA.JK", sentiment=Sentiment.BULLISH, score=0.6,
        confidence=0.85, news_count=5, last_updated=datetime.now()
    )
    sample_dashboard = QuantDashboard(
        strong_buy=[], buy=[], hold=[], sell=[], strong_sell=[],
        market_breadth=0.55, avg_composite_score=0.1, generated_at=datetime.now()
    )

    market_mock.get_realtime_data.return_value = [sample_md]
    market_mock.get_top_movers.return_value = {"gainers": [], "losers": [], "active": [], "timestamp": ""}
    market_mock.get_all_assets.return_value = {"stocks": [sample_md], "commodities": [], "indices": [], "timestamp": ""}
    market_mock.get_market_overview.return_value = {
        "ihsg": {"index": "IHSG", "price": 7000, "change": 10, "change_percent": 0.1, "volume": 100000, "timestamp": ""},
        "market_breadth": {"advancing": 200, "declining": 100, "unchanged": 50, "total": 350, "breadth_ratio": 0.57, "sentiment": "bullish"},
        "timestamp": ""
    }
    market_mock.get_watchlist.return_value = {"stocks": ["BBCA.JK"], "commodities": [], "indices": []}
    market_mock.get_symbol_info.return_value = {"symbol": "BBCA.JK", "name": "Bank Central Asia"}

    sentiment_mock.analyze_news_sentiment.return_value = [sample_sa]
    sentiment_mock.get_sentiment_dashboard.return_value = {"total": 1, "bullish": 1}
    sentiment_mock.analyze_single_symbol.return_value = sample_sa

    prediction_mock.generate_signals.return_value = []
    prediction_mock.get_quant_dashboard.return_value = sample_dashboard
    prediction_mock.analyze_symbol.return_value = None

    chatbot_mock.process_message = AsyncMock(return_value=MagicMock(
        response="Test response",
        sources=[],
        timestamp=datetime.now()
    ))

    import backend.main as main_module
    main_module.market_agent = market_mock
    main_module.sentiment_agent = sentiment_mock
    main_module.prediction_agent = prediction_mock
    main_module.chatbot = chatbot_mock

    client = TestClient(main_module.app)
    return client



# ── Tests ─────────────────────────────────────────────────────────────────────

class TestRootEndpoint:
    def test_root_returns_200(self, app_client):
        resp = app_client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["app"] == "NusaTerminal API"
        assert data["status"] == "running"


class TestHealthEndpoint:
    def test_health_returns_200(self, app_client):
        resp = app_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "chatbot_stats" in data


class TestMarketEndpoints:
    def test_get_market_data(self, app_client):
        resp = app_client.get("/api/market")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert data[0]["symbol"] == "BBCA.JK"

    def test_get_market_with_filter(self, app_client):
        resp = app_client.get("/api/market?symbols=BBCA.JK")
        assert resp.status_code == 200

    def test_get_market_movers(self, app_client):
        resp = app_client.get("/api/market/movers")
        assert resp.status_code == 200
        data = resp.json()
        assert "gainers" in data
        assert "losers" in data
        assert "active" in data

    def test_get_all_assets(self, app_client):
        resp = app_client.get("/api/market/all")
        assert resp.status_code == 200
        data = resp.json()
        assert "stocks" in data

    def test_get_market_overview(self, app_client):
        resp = app_client.get("/api/market/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert "ihsg" in data
        assert "market_breadth" in data

    def test_get_watchlist(self, app_client):
        resp = app_client.get("/api/market/watchlist")
        assert resp.status_code == 200
        data = resp.json()
        assert "stocks" in data

    def test_get_symbol_info(self, app_client):
        resp = app_client.get("/api/market/info/BBCA.JK")
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "BBCA.JK"

    def test_get_ihsg(self, app_client):
        resp = app_client.get("/api/market/ihsg")
        assert resp.status_code == 200


class TestSentimentEndpoints:
    def test_get_sentiment(self, app_client):
        resp = app_client.get("/api/sentiment")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_get_sentiment_dashboard(self, app_client):
        resp = app_client.get("/api/sentiment/dashboard")
        assert resp.status_code == 200

    def test_get_symbol_sentiment(self, app_client):
        resp = app_client.get("/api/sentiment/BBCA.JK")
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "BBCA.JK"


class TestSignalEndpoints:
    def test_get_signals(self, app_client):
        resp = app_client.get("/api/signals")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_get_signals_dashboard(self, app_client):
        resp = app_client.get("/api/signals/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "strong_buy" in data
        assert "market_breadth" in data


class TestChatEndpoints:
    def test_chat_post(self, app_client):
        resp = app_client.post("/api/chat", json={
            "message": "Bagaimana kondisi BBCA hari ini?",
            "user_id": "test_user"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "response" in data
        assert "timestamp" in data

    def test_chat_empty_message(self, app_client):
        resp = app_client.post("/api/chat", json={"message": ""})
        assert resp.status_code == 200

    def test_chat_stats(self, app_client):
        resp = app_client.get("/api/chat/stats")
        assert resp.status_code == 200
