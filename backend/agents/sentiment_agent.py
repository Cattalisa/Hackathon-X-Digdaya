"""
Sentiment Agent - NusaTerminal
Menggunakan IndoBERT (atau fallback ke multilingual BERT) untuk analisis sentimen berita
berbasis AI model, bukan keyword matching.

CHANGELOG:
  FIX-1: ensure_model_loaded() menggunakan threading.Event — tidak lagi polling
          flag _loading yang tidak pernah di-set dari background thread.
  FIX-2: Label map mdhugol DIPERBAIKI (sebelumnya terbalik):
          LABEL_0 = positive (bukan negative)
          LABEL_2 = negative (bukan positive)
          Referensi: https://huggingface.co/mdhugol/indonesia-bert-sentiment-classification
  FIX-3: Exception di pipeline call kini di-print langsung ke stderr (bukan hanya
          logger.error yang mungkin tidak tampil) agar mudah didiagnosa.
  FIX-4: _analyze_single_text mengembalikan 'score' (nilai sentimen 0/0.5/1.0) dan
          'confidence' (keyakinan model 0-1) secara eksplisit terpisah.
  FIX-5: analyze_news_sentiment memanggil ensure_model_loaded() di awal agar
          batch analisis tidak mulai sebelum model siap.
"""

import sys
import threading
from datetime import datetime
from typing import List, Dict, Optional
from ..models.schemas import NewsArticle, SentimentAnalysis, Sentiment
from ..services.news_service import NewsService
import logging

logger = logging.getLogger(__name__)


# ── Singleton ─────────────────────────────────────────────────────────────────
_SENTIMENT_AGENT_INSTANCE = None

def get_sentiment_agent() -> "SentimentAgent":
    """
    Kembalikan singleton SentimentAgent.
    Selalu gunakan fungsi ini — jangan buat SentimentAgent() langsung.
    """
    global _SENTIMENT_AGENT_INSTANCE
    if _SENTIMENT_AGENT_INSTANCE is None:
        _SENTIMENT_AGENT_INSTANCE = SentimentAgent()
    return _SENTIMENT_AGENT_INSTANCE


class SentimentAgent:
    """
    Agent analisis sentimen berbasis IndoBERT untuk berita pasar modal Indonesia.

    Gunakan get_sentiment_agent() untuk mendapatkan instance singleton.
    """

    MODEL_OPTIONS = [
        "mdhugol/indonesia-bert-sentiment-classification",
        "w11wo/indonesian-roberta-base-sentiment-classifier",
        "nlptown/bert-base-multilingual-uncased-sentiment",
    ]

    # FIX-2: Label map DIPERBAIKI sesuai dokumentasi resmi tiap model.
    # mdhugol: LABEL_0=positive, LABEL_1=neutral, LABEL_2=negative
    # (Kode lama salah: LABEL_0=negative, LABEL_2=positive — TERBALIK)
    LABEL_MAPS = {
        "mdhugol/indonesia-bert-sentiment-classification": {
            "LABEL_0": "positive",   # FIX: sebelumnya "negative"
            "LABEL_1": "neutral",
            "LABEL_2": "negative",   # FIX: sebelumnya "positive"
        },
        "w11wo/indonesian-roberta-base-sentiment-classifier": {
            "LABEL_0": "negative",
            "LABEL_1": "neutral",
            "LABEL_2": "positive",
            "negative": "negative",
            "neutral":  "neutral",
            "positive": "positive",
            "NEGATIVE": "negative",
            "NEUTRAL":  "neutral",
            "POSITIVE": "positive",
        },
        "nlptown/bert-base-multilingual-uncased-sentiment": {
            "1 star":  "negative",
            "2 stars": "negative",
            "3 stars": "neutral",
            "4 stars": "positive",
            "5 stars": "positive",
        },
    }

    def __init__(self):
        self.news_service = NewsService()
        self.model_name = None
        self.sentiment_pipeline = None
        self.label_map = {}
        # FIX-1: Pakai threading.Event untuk sinkronisasi yang benar
        self._model_ready_event = threading.Event()
        # Load model di background agar tidak block startup
        t = threading.Thread(target=self._load_model, daemon=True)
        t.start()

    def _load_model(self):
        """Load model sentiment dengan fallback strategy."""
        try:
            from transformers import pipeline
        except Exception as e:
            print(f"[SentimentAgent] CRITICAL: transformers import gagal: {e}", file=sys.stderr)
            self._model_ready_event.set()
            return

        try:
            import torch
            device = 0 if torch.cuda.is_available() else -1
        except Exception:
            device = -1

        for model_name in self.MODEL_OPTIONS:
            try:
                logger.info(f"Mencoba load model: {model_name}")
                self.sentiment_pipeline = pipeline(
                    "text-classification",
                    model=model_name,
                    tokenizer=model_name,
                    device=device,
                    truncation=True,
                    max_length=512,
                )
                self.model_name = model_name
                self.label_map = self.LABEL_MAPS.get(model_name, {})
                logger.info(f"✅ Model berhasil dimuat: {model_name}")
                logger.info(f"   Label map aktif: {self.label_map}")
                break
            except Exception as e:
                logger.warning(f"Gagal load {model_name}: {e}")
                continue
        else:
            msg = (
                "CRITICAL: Tidak ada AI sentiment model yang berhasil dimuat! "
                "Sentiment akan selalu fallback ke neutral (0.5)."
            )
            logger.error(msg)
            print(f"[SentimentAgent] {msg}", file=sys.stderr)

        # FIX-1: Signal bahwa loading selesai (berhasil atau gagal)
        self._model_ready_event.set()

    def ensure_model_loaded(self, timeout: int = 120):
        """
        Tunggu sampai model siap (max timeout detik).
        FIX-1: Menggunakan threading.Event.wait() yang benar.
        """
        if self.sentiment_pipeline:
            return
        logger.info("Menunggu model sentiment selesai load...")
        loaded = self._model_ready_event.wait(timeout=timeout)
        if loaded:
            logger.info("Model siap setelah menunggu")
        else:
            logger.warning(f"Timeout {timeout}s menunggu model sentiment — akan pakai fallback")

    def _normalize_label(self, raw_label: str, confidence: float) -> tuple:
        """
        Normalisasi raw label dari model ke positive/neutral/negative.
        Returns: (normalized_label, confidence)
        """
        if self.label_map:
            normalized = self.label_map.get(raw_label, raw_label).lower()
        else:
            normalized = raw_label.lower()
            if "pos" in normalized:
                normalized = "positive"
            elif "neg" in normalized:
                normalized = "negative"
            else:
                normalized = "neutral"
        return normalized, confidence

    def _label_to_score(self, label: str) -> float:
        """Konversi label ke nilai numerik: positive=1.0, neutral=0.5, negative=0.0"""
        return {"positive": 1.0, "neutral": 0.5, "negative": 0.0}.get(label, 0.5)

    def _analyze_single_text(self, text: str) -> Dict:
        """
        Analisis sentimen satu teks.
        FIX-3 & FIX-4: Error dicetak ke stderr, return dict memiliki 'score' dan 'confidence' terpisah.

        Returns dict:
          label      : "positive" / "neutral" / "negative"
          score      : nilai sentimen numerik (0.0 / 0.5 / 1.0)
          confidence : keyakinan model (0.0–1.0, nilai asli dari softmax)
        """
        if not self.sentiment_pipeline:
            self.ensure_model_loaded()

        if not self.sentiment_pipeline:
            print("[SentimentAgent] WARNING: pipeline masih None setelah tunggu — pakai fallback", file=sys.stderr)
            return {"label": "neutral", "score": 0.5, "confidence": 0.5}

        # Truncate aman berdasarkan jumlah kata (BERT ~512 token ≈ 150-200 kata)
        words = text.split()
        if len(words) > 150:
            text = " ".join(words[:150])

        try:
            raw = self.sentiment_pipeline(text)[0]
            label, confidence = self._normalize_label(raw["label"], raw["score"])
            score = self._label_to_score(label)
            return {"label": label, "score": score, "confidence": confidence}
        except Exception as e:
            # FIX-3: Print ke stderr agar selalu terlihat
            print(f"[SentimentAgent] ERROR pipeline: {type(e).__name__}: {e}", file=sys.stderr)
            print(f"[SentimentAgent]   teks: {text[:100]}", file=sys.stderr)
            logger.error(f"Error analisis sentimen: {e} | teks: {text[:80]}")
            return {"label": "neutral", "score": 0.5, "confidence": 0.5}

    def _aggregate_article_sentiment(self, article: NewsArticle) -> Dict:
        """
        Gabungkan sentimen judul (60%) + summary (40%) satu artikel.
        FIX-4: 'confidence' dari model dipakai secara benar, tidak dicampur dengan 'score'.
        """
        title_analysis = self._analyze_single_text(article.title)

        if article.summary:
            summary_analysis = self._analyze_single_text(article.summary[:300])
        else:
            summary_analysis = title_analysis

        # Weighted average nilai sentimen numerik
        weighted_score = (title_analysis["score"] * 0.6) + (summary_analysis["score"] * 0.4)
        # Weighted average keyakinan model (confidence)
        weighted_conf = (title_analysis["confidence"] * 0.6) + (summary_analysis["confidence"] * 0.4)

        if weighted_score >= 0.65:
            final_label = "positive"
        elif weighted_score <= 0.35:
            final_label = "negative"
        else:
            final_label = "neutral"

        return {
            "label": final_label,
            "score": weighted_score,
            "confidence": weighted_conf,
            "title_sentiment": title_analysis["label"],
            "summary_sentiment": summary_analysis["label"],
        }

    def analyze_news_sentiment(
        self,
        news_articles: Optional[List[NewsArticle]] = None,
        symbols: Optional[List[str]] = None
    ) -> List[SentimentAnalysis]:
        """
        Analisis sentimen kumpulan berita.
        FIX-5: ensure_model_loaded() dipanggil di awal.
        """
        self.ensure_model_loaded()  # FIX-5: tunggu model sebelum batch

        if news_articles is None:
            news_articles = self.news_service.fetch_news(limit=50)

        if not news_articles:
            return []

        norm_symbols = None
        if symbols:
            norm_symbols = set()
            for s in symbols:
                su = s.upper()
                norm_symbols.add(su)
                if not su.endswith('.JK'):
                    norm_symbols.add(f"{su}.JK")
                else:
                    norm_symbols.add(su.replace('.JK', ''))

        symbol_articles: Dict[str, List[NewsArticle]] = {}

        for article in news_articles:
            article_symbols = article.symbols if article.symbols else ["MARKET"]

            if norm_symbols is not None:
                filtered = []
                for s in article_symbols:
                    su = s.upper()
                    if su in norm_symbols or su.replace('.JK', '') in norm_symbols:
                        filtered.append(s)
                if filtered:
                    article_symbols = filtered
                else:
                    if not article.symbols:
                        article_symbols = list(norm_symbols)
                    else:
                        continue

            for sym in article_symbols:
                if sym not in symbol_articles:
                    symbol_articles[sym] = []
                symbol_articles[sym].append(article)

        results = []

        for symbol, articles in symbol_articles.items():
            if not articles:
                continue

            article_sentiments = []
            for article in articles[:10]:
                sentiment_result = self._aggregate_article_sentiment(article)
                article_sentiments.append(sentiment_result)
                article.sentiment_score = sentiment_result["score"]

            if not article_sentiments:
                continue

            avg_score = sum(s["score"] for s in article_sentiments) / len(article_sentiments)
            avg_confidence = sum(s["confidence"] for s in article_sentiments) / len(article_sentiments)

            if avg_score >= 0.6:
                final_sentiment = Sentiment.BULLISH
            elif avg_score <= 0.4:
                final_sentiment = Sentiment.BEARISH
            else:
                final_sentiment = Sentiment.NEUTRAL

            normalized_score = (avg_score - 0.5) * 2

            results.append(SentimentAnalysis(
                symbol=symbol,
                sentiment=final_sentiment,
                score=round(normalized_score, 4),
                confidence=round(avg_confidence, 4),
                news_count=len(articles),
                last_updated=datetime.now()
            ))

        return results

    def analyze_single_symbol(self, symbol: str, limit: int = 20) -> Optional[SentimentAnalysis]:
        """Analisis sentimen untuk satu simbol spesifik."""
        symbol_news = self.news_service.fetch_news_by_symbol(symbol, limit=limit)
        if not symbol_news:
            return None

        results = self.analyze_news_sentiment(news_articles=symbol_news, symbols=[symbol])

        req = symbol.upper()
        candidates = {req}
        if not req.endswith('.JK'):
            candidates.add(f"{req}.JK")
        else:
            candidates.add(req.replace('.JK', ''))

        for r in results:
            if r.symbol in candidates or r.symbol.replace('.JK', '') in candidates:
                return r

        return results[0] if results else None

    def get_sentiment_dashboard(self) -> Dict:
        """Ringkasan sentimen semua simbol untuk dashboard."""
        all_sentiments = self.analyze_news_sentiment()

        bullish = [s for s in all_sentiments if s.sentiment == Sentiment.BULLISH]
        bearish = [s for s in all_sentiments if s.sentiment == Sentiment.BEARISH]
        neutral = [s for s in all_sentiments if s.sentiment == Sentiment.NEUTRAL]

        most_discussed = sorted(all_sentiments, key=lambda x: x.news_count, reverse=True)

        return {
            "bullish_count": len(bullish),
            "bearish_count": len(bearish),
            "neutral_count": len(neutral),
            "total_analyzed": len(all_sentiments),
            "most_discussed": most_discussed[:5],
            "strongest_bullish": sorted(bullish, key=lambda x: x.score, reverse=True)[:3],
            "strongest_bearish": sorted(bearish, key=lambda x: x.score)[:3],
            "model_used": self.model_name,
            "timestamp": datetime.now()
        }
