"""
CHUNK 2 - Unit Tests: Pydantic Schemas
Tests that schemas validate correctly, handle edge cases, and serialize properly.
"""
import pytest
from datetime import datetime
from backend.models.schemas import (
    MarketData, MarketType, Sentiment, Signal,
    SentimentAnalysis, QuantSignal, QuantDashboard,
    TechnicalFactors, MomentumFactors, VolumeFactors,
    ChatMessage, ChatResponse, NewsArticle
)


class TestMarketData:
    def test_basic_creation(self, sample_market_data):
        """MarketData can be created with valid fields."""
        md = sample_market_data
        assert md.symbol == "BBCA.JK"
        assert md.price == 6175.0
        assert md.market_type == MarketType.STOCK

    def test_market_type_enum(self):
        """MarketType enum has correct values."""
        assert MarketType.STOCK.value == "stock"
        assert MarketType.COMMODITY.value == "commodity"
        assert MarketType.INDEX.value == "index"

    def test_json_serialization(self, sample_market_data):
        """MarketData serializes to JSON without errors."""
        json_str = sample_market_data.model_dump_json()
        assert "BBCA" in json_str
        assert "6175" in json_str

    def test_zero_price_allowed(self):
        """MarketData with zero price is valid (fallback case)."""
        md = MarketData(
            symbol="TEST.JK", name="Test", price=0.0,
            change=0.0, change_percent=0.0, volume=0,
            open=0.0, high=0.0, low=0.0, close=0.0,
            last_update=datetime.now()
        )
        assert md.price == 0.0


class TestSentimentAnalysis:
    def test_basic_creation(self, sample_sentiment):
        assert sample_sentiment.symbol == "BBCA.JK"
        assert sample_sentiment.sentiment == Sentiment.BULLISH
        assert 0 <= sample_sentiment.score <= 1
        assert 0 <= sample_sentiment.confidence <= 1

    def test_sentiment_enum_values(self):
        assert Sentiment.BULLISH.value == "bullish"
        assert Sentiment.BEARISH.value == "bearish"
        assert Sentiment.NEUTRAL.value == "neutral"


class TestSignalEnum:
    def test_signal_values(self):
        assert Signal.STRONG_BUY.value == "strong_buy"
        assert Signal.BUY.value == "buy"
        assert Signal.HOLD.value == "hold"
        assert Signal.SELL.value == "sell"
        assert Signal.STRONG_SELL.value == "strong_sell"


class TestChatSchemas:
    def test_chat_message_defaults(self):
        msg = ChatMessage(message="Bagaimana BBCA hari ini?")
        assert msg.user_id == "default"
        assert msg.context is None

    def test_chat_response(self):
        resp = ChatResponse(
            response="BBCA naik 2%",
            sources=["https://cnbcindonesia.com"],
            timestamp=datetime.now()
        )
        assert resp.response == "BBCA naik 2%"
        assert len(resp.sources) == 1


class TestNewsArticle:
    def test_news_article_creation(self):
        article = NewsArticle(
            id="abc123",
            title="BBCA Cetak Laba Tertinggi",
            summary="Bank Central Asia mencatat rekor laba bersih",
            source="CNBC Indonesia",
            url="https://cnbcindonesia.com/bbca-laba",
            published_at=datetime.now(),
            symbols=["BBCA.JK"],
            sentiment_score=0.7
        )
        assert article.symbols == ["BBCA.JK"]
        assert article.sentiment_score == 0.7
