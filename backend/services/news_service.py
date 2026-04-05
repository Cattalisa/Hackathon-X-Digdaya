"""
NusaTerminal - News Service
Scraping berita keuangan dari RSS feeds media Indonesia.
Menggunakan feedparser + fallback ke requests jika newspaper4k gagal.
"""

import os
import feedparser
import re
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from email.utils import parsedate_to_datetime

import aiohttp
import asyncio
import urllib.parse

from ..models.schemas import NewsArticle
from ..services.data_service import INDONESIAN_STOCKS, COMMODITIES, INDICES, DataService

logger = logging.getLogger(__name__)


# ─── RSS FEEDS ────────────────────────────────────────────────────────────────

# ─── WHITELIST RSS FEEDS (hanya media keuangan/bisnis) ──────────────────────
# PENTING: Hanya gunakan media yang fokus pada keuangan dan pasar modal.
# Jangan tambahkan media umum (Kompas, Liputan6, Tribun) karena akan
# menyebabkan berita non-finansial masuk dan merusak analisis sentimen.
RSS_FEEDS: dict = {
    "cnbc_market":    "https://www.cnbcindonesia.com/market/rss",
    "cnbc_news":      "https://www.cnbcindonesia.com/news/rss",
    "kontan":         "https://www.kontan.co.id/rss/investasi.rss",
    "kontan_saham":   "https://investasi.kontan.co.id/rss/saham.rss",
    "bisnis_market":  "https://market.bisnis.com/rss/index/10",
    "bisnis_keuangan":"https://finansial.bisnis.com/rss/index/7",
    "investing_id":   "https://id.investing.com/rss/news_301.rss",
    "tempo_bisnis":   "https://bisnis.tempo.co/rss",
    "detik_finance":  "https://rss.detik.com/index.php/detikcom_finance",
    "kompas_money":   "https://money.kompas.com/rss",
    "investor_id":    "https://investor.id/feed",
    "investing":      "https://id.investing.com/rss/news.rss",
}

# Default limits (can be adjusted via env)
DEFAULT_MAX_PER_FEED = int(os.getenv("NEWS_MAX_PER_FEED", "60"))
DEFAULT_TOTAL_FETCH_LIMIT = int(os.getenv("NEWS_TOTAL_FETCH_LIMIT", "1000"))
DEFAULT_NEWS_MAX_AGE_DAYS = int(os.getenv("NEWS_MAX_AGE_DAYS", "7"))
# Default lookback for symbol-specific searches (extend to 30 days)
DEFAULT_SYMBOL_MAX_AGE_DAYS = int(os.getenv("NEWS_SYMBOL_MAX_AGE_DAYS", "30"))

# Map nama perusahaan/keyword → simbol saham IDX
COMPANY_TO_SYMBOL: dict = {
    # Perbankan
    "bca": "BBCA.JK", "bank central asia": "BBCA.JK",
    "bri": "BBRI.JK", "bank rakyat": "BBRI.JK",
    "mandiri": "BMRI.JK", "bank mandiri": "BMRI.JK",
    "bni": "BBNI.JK", "bank negara": "BBNI.JK",
    # Telco & Tech
    "telkom": "TLKM.JK",
    "goto": "GOTO.JK", "gojek": "GOTO.JK", "tokopedia": "GOTO.JK",
    # Industri
    "astra": "ASII.JK",
    "unilever": "UNVR.JK",
    "indofood": "INDF.JK", "icbp": "ICBP.JK",
    "kalbe": "KLBF.JK",
    # Tambang & Energi
    "antam": "ANTM.JK", "aneka tambang": "ANTM.JK",
    "antam tbk": "ANTM.JK", "pt aneka tambang": "ANTM.JK",
    "bukit asam": "PTBA.JK", "ptba": "PTBA.JK",
    "adaro": "ADRO.JK",
    # Komoditas
    "emas": "GC=F", "gold": "GC=F",
    "minyak": "CL=F", "crude oil": "CL=F",
    "cpo": "FCPO.BMD", "sawit": "FCPO.BMD", "palm oil": "FCPO.BMD",
    # Indeks
    "ihsg": "^JKSE", "bursa efek": "^JKSE", "idx": "^JKSE",
    "composite": "^JKSE",
}

# Pattern regex untuk simbol saham format XXXX.JK (1-5 huruf lebih fleksibel)
SYMBOL_PATTERN = re.compile(r'\b([A-Z]{1,5})\.JK\b')

# Words that indicate a financial/stock article.
# Dipakai di DUA tempat:
#   1. _parse_feed() → filter artikel non-finansial sebelum masuk pool
#   2. fetch_news_by_symbol() → post-filter loosely-matched articles
FINANCIAL_KEYWORDS = {
    # Pasar modal & instrumen
    "tbk", "saham", "bursa", "bei", "idx", "ihsg", "dividen",
    "laba", "emiten", "ipo", "pasar modal", "right issue", "buyback",
    "delisting", "listing", "obligasi", "reksa dana", "sukuk",
    # Ekonomi makro
    "keuangan", "investasi", "investor", "inflasi", "deflasi",
    "suku bunga", "bi rate", "rupiah", "nilai tukar", "kurs",
    "ekspor", "impor", "neraca", "apbn", "apbd", "gdp", "pdb",
    "resesi", "pertumbuhan ekonomi", "fiskal", "moneter",
    # Korporasi & bisnis
    "perusahaan", "korporasi", "merger", "akuisisi", "divestasi",
    "laporan keuangan", "pendapatan", "revenue", "profit", "rugi",
    "utang", "aset", "modal", "likuiditas", "kredit", "pinjaman",
    "bank", "asuransi", "leasing", "multifinance",
    # Regulator & lembaga
    "ojk", "bi rate", "kemenkeu", "bapepam", "lps", "bumn",
    # Komoditas
    "komoditas", "emas", "minyak", "batu bara", "nikel", "sawit",
    "cpo", "timah", "tembaga", "karet", "kopi", "kakao",
    # Nama perusahaan / entitas IDX sering disebut
    "bca", "bri", "mandiri", "bni", "telkom", "astra", "unilever",
    "pertamina", "pln", "garuda", "antam", "goto", "tokopedia",
    "gojek", "indofood", "kalbe", "adaro", "ptba",
    # Sinyal berita bisnis
    "harga", "naik", "turun", "anjlok", "melonjak", "stagnan",
    "target", "proyeksi", "kinerja", "kuartal", "semester", "tahunan",
    "miliar", "triliun", "juta", "rp", "usd", "dolar",
}


class NewsService:
    """
    Service untuk scraping berita keuangan dari RSS feeds.
    Mengekstrak simbol saham yang disebut di setiap berita.
    """

    def __init__(self):
        self._cache: Optional[List[NewsArticle]] = None
        self._cache_time: Optional[datetime] = None
        self._cache_ttl_minutes = 10  # Cache 10 menit
        # DataService instance for dynamic symbol list
        try:
            self._ds = DataService()
        except Exception:
            self._ds = None
        self._all_symbols = None
        self._all_symbols_time = None

    def _get_all_symbols(self) -> dict:
        # Cache all-symbols for 24 hours to avoid repeated remote calls
        try:
            if self._all_symbols and self._all_symbols_time:
                if (datetime.now() - self._all_symbols_time).total_seconds() < 24 * 3600:
                    return self._all_symbols
            if self._ds:
                all_syms = self._ds.get_all_symbols()
            else:
                all_syms = {**INDONESIAN_STOCKS, **COMMODITIES, **INDICES}
            self._all_symbols = all_syms
            self._all_symbols_time = datetime.now()
            return all_syms
        except Exception:
            return {**INDONESIAN_STOCKS, **COMMODITIES, **INDICES}

    def _is_cache_valid(self) -> bool:
        if not self._cache or not self._cache_time:
            return False
        elapsed = (datetime.now() - self._cache_time).total_seconds() / 60
        return elapsed < self._cache_ttl_minutes

    def _parse_date(self, entry) -> datetime:
        """Parse tanggal dari berbagai format RSS entry."""
        try:
            if hasattr(entry, "published"):
                return parsedate_to_datetime(entry.published).replace(tzinfo=None)
        except Exception:
            pass

        try:
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                return datetime(*entry.published_parsed[:6])
        except Exception:
            pass

        return datetime.now()

    def _extract_symbols(self, text: str, known_tickers: Optional[set] = None) -> List[str]:
        """
        Ekstrak simbol saham dari teks berita.

        Strategi (ketat ke longgar):
        1. Format eksplisit XXXX.JK langsung di teks → langsung accept
        2. COMPANY_TO_SYMBOL (dikurasi manual) → accept dengan word-boundary match
        3. Dynamic ALL_SYMBOLS lookup → HANYA accept jika nama perusahaan
           terdiri dari ≥2 kata ATAU mengandung financial keyword (Tbk, PT, dll)
           Ini mencegah false positive dari nama pendek/ambigu seperti "Bayan"

        Args:
            known_tickers: Set simbol yang sedang dicari (dari fetch_news_by_symbol).
                           Jika diberikan, hanya simbol dalam set ini yang dicari
                           dari dynamic lookup — ini untuk query spesifik user.
        """
        symbols = set()
        text_lower = text.lower()

        # ── Layer 1: Format XXXX.JK eksplisit di teks ────────────────────────
        # Ini paling reliabel — simbol langsung disebut di berita
        all_known = {**INDONESIAN_STOCKS, **COMMODITIES, **INDICES}
        for match in SYMBOL_PATTERN.findall(text.upper()):
            full_sym = f"{match}.JK"
            if full_sym in all_known:
                symbols.add(full_sym)

        # ── Layer 2: COMPANY_TO_SYMBOL yang dikurasi ─────────────────────────
        for name, symbol in COMPANY_TO_SYMBOL.items():
            try:
                pattern = re.compile(r"\b" + re.escape(name) + r"\b", re.IGNORECASE)
                if pattern.search(text_lower):
                    symbols.add(symbol)
            except Exception:
                continue

        # ── Layer 3: Dynamic ALL_SYMBOLS — dengan validasi ketat ─────────────
        # Hanya digunakan jika ada known_tickers (artinya ini query spesifik user)
        # atau nama perusahaan memenuhi syarat keamanan: ≥2 kata + financial signal
        try:
            dynamic_syms = self._get_all_symbols()
            # Tentukan scope: kalau known_tickers diberikan, cari hanya simbol itu
            scope = {k: v for k, v in dynamic_syms.items()
                     if known_tickers is None or k in known_tickers}

            for sym, company_name in scope.items():
                if not company_name or sym in symbols:
                    continue

                name_lower = company_name.lower()
                words = name_lower.split()

                # Syarat keamanan:
                # A) Nama ≥ 2 kata (menghindari nama pendek ambigu seperti "Bayan")
                # B) ATAU mengandung "tbk" / "pt " yang menandakan perusahaan IDX
                # C) ATAU simbol ini ada di known_tickers (user memang nyari ini)
                is_multi_word = len(words) >= 2
                has_corporate_marker = any(w in name_lower for w in ("tbk", " pt ", "pt."))
                is_explicit_target = known_tickers and sym in known_tickers

                if not (is_multi_word or has_corporate_marker or is_explicit_target):
                    continue  # Skip nama pendek ambigu

                try:
                    pattern = re.compile(r"\b" + re.escape(name_lower) + r"\b", re.IGNORECASE)
                    if pattern.search(text_lower):
                        symbols.add(sym)
                except Exception:
                    continue
        except Exception:
            pass

        return list(symbols)

    def _make_article_id(self, url: str, source: str) -> str:
        """Buat ID unik dari URL artikel."""
        return hashlib.md5(f"{source}_{url}".encode()).hexdigest()[:16]

    def _get_source_name(self, key: str) -> str:
        names = {
            "cnbc_market":  "CNBC Indonesia",
            "cnbc_news":    "CNBC Indonesia",
            "kontan":       "Kontan",
            "kontan_saham": "Kontan Investasi",
            "bisnis":       "Bisnis.com",
            "investing_id": "Investing.com ID",
        }
        return names.get(key, key)

    def _parse_feed(self, source_name: str, rss_url: str, max_per_feed: int = 50) -> List[NewsArticle]:
        """Parse satu RSS feed dan return list NewsArticle."""
        articles = []

        try:
            feed = feedparser.parse(rss_url)

            for entry in feed.entries[:max_per_feed]:
                try:
                    title = entry.get("title", "").strip()
                    if not title:
                        continue

                    summary = entry.get("summary", "") or entry.get("description", "")
                    # Bersihkan HTML tags dari summary
                    summary = re.sub(r"<[^>]+>", "", summary).strip()
                    summary = summary[:500] if summary else ""

                    url = entry.get("link", "")
                    published_at = self._parse_date(entry)

                    # Ekstrak simbol dari judul + summary
                    full_text = f"{title} {summary}"
                    symbols = self._extract_symbols(full_text)

                    # ── FILTER FINANSIAL ─────────────────────────────────────
                    # Buang artikel yang tidak relevan dengan keuangan/pasar modal.
                    # Artikel lolos jika: ada simbol saham terdeteksi, ATAU
                    # judul/summary mengandung minimal 1 financial keyword.
                    full_text_lower = full_text.lower()
                    is_financial = bool(symbols) or any(
                        kw in full_text_lower for kw in FINANCIAL_KEYWORDS
                    )
                    if not is_financial:
                        logger.debug(f"Skip non-finansial: {title[:60]}")
                        continue

                    article = NewsArticle(
                        id=self._make_article_id(url, source_name),
                        title=title,
                        summary=summary,
                        source=self._get_source_name(source_name),
                        url=url,
                        published_at=published_at,
                        symbols=symbols,
                        sentiment_score=0.0,  # Diisi oleh SentimentAgent
                    )
                    articles.append(article)

                except Exception as e:
                    logger.debug(f"Skip entry dari {source_name}: {e}")
                    continue

        except Exception as e:
            logger.warning(f"Gagal parse RSS {source_name} ({rss_url}): {e}")

        return articles

    def fetch_news(self, limit: int = 250, compute_sentiment: bool = False, max_age_days: Optional[int] = None, max_per_feed_override: Optional[int] = None) -> List[NewsArticle]:
        """
        Fetch berita terbaru dari semua RSS feeds.
        Hasil di-cache 10 menit untuk menghindari spam request.
        
        Args:
            limit: Jumlah maksimal artikel yang dikembalikan
            
        Returns:
            List NewsArticle diurutkan dari terbaru
        """
        if self._is_cache_valid() and self._cache:
            # If caller requested per-article sentiment, compute it even when
            # returning cached results. This avoids returning stale articles
            # with sentiment_score still at the default 0.0 when callers
            # expect scores to be present.
            result = self._cache[:limit]
            if compute_sentiment and result:
                try:
                    # Lazy import to avoid circular import at module init
                    from .. import main as app_main
                    sentiment_agent = getattr(app_main, "sentiment_agent", None)
                except Exception:
                    sentiment_agent = None

                if sentiment_agent:
                    for article in result:
                        try:
                            # Only compute if not already set (0.0 is considered unset)
                            if not article.sentiment_score:
                                analysis = sentiment_agent._aggregate_article_sentiment(article)
                                article.sentiment_score = analysis.get("score", 0.0)
                        except Exception:
                            continue

            return result

        all_articles: List[NewsArticle] = []

        # Ambil lebih banyak artikel per feed agar tersedia lebih banyak kandidat
        max_per_feed = max_per_feed_override if max_per_feed_override is not None else DEFAULT_MAX_PER_FEED
        for source_key, rss_url in RSS_FEEDS.items():
            articles = self._parse_feed(source_key, rss_url, max_per_feed=max_per_feed)
            all_articles.extend(articles)
            logger.debug(f"  {source_key}: {len(articles)} artikel (max_per_feed={max_per_feed})")

        # Deduplikasi berdasarkan ID
        seen_ids = set()
        unique_articles = []
        for article in all_articles:
            if article.id not in seen_ids:
                seen_ids.add(article.id)
                unique_articles.append(article)

        # Sort terbaru dulu
        unique_articles.sort(key=lambda x: x.published_at, reverse=True)

        logger.info(f"Fetched {len(unique_articles)} berita dari {len(RSS_FEEDS)} sumber")

        # Filter articles to a recent window (default: last DEFAULT_NEWS_MAX_AGE_DAYS)
        try:
            days = max_age_days if max_age_days is not None else DEFAULT_NEWS_MAX_AGE_DAYS
            cutoff = datetime.now() - timedelta(days=days)
            recent_articles = [a for a in unique_articles if a.published_at >= cutoff]
        except Exception:
            recent_articles = unique_articles

        logger.info(f"{len(recent_articles)} berita berada dalam rentang {days} hari")

        # Update cache with the recent window
        self._cache = recent_articles
        self._cache_time = datetime.now()

        result = recent_articles[:limit]

        # Optionally compute per-article sentiment scores using the global
        # SentimentAgent instance (if available). This is a potentially heavy
        # operation and is only run when `compute_sentiment=True` is requested
        # by callers such as the API endpoints.
        if compute_sentiment and result:
            # Gunakan singleton SentimentAgent langsung — tidak import main.py
            # karena news_service bisa dipanggil di luar context FastAPI app.
            sentiment_agent = None
            try:
                from ..agents.sentiment_agent import get_sentiment_agent
                sentiment_agent = get_sentiment_agent()
                sentiment_agent.ensure_model_loaded(timeout=60)
            except Exception:
                pass

            if sentiment_agent and sentiment_agent.sentiment_pipeline:
                for article in result:
                    try:
                        analysis = sentiment_agent._aggregate_article_sentiment(article)
                        # FIX: default 0.5 (neutral), bukan 0.0 jika gagal
                        article.sentiment_score = analysis.get("score", 0.5)
                    except Exception:
                        article.sentiment_score = 0.5

        return result

    def fetch_news_by_symbol(self, symbol: str, limit: int = 20, compute_sentiment: bool = True) -> List[NewsArticle]:
        """Fetch berita yang menyebut simbol tertentu.

        Behavior:
        - Cari di pool berita yang lebih besar (DEFAULT_TOTAL_FETCH_LIMIT)
        - Kembalikan hasil yang sudah dikategorikan (`a.symbols`) dahulu
        - Jika kurang dari 5 artikel ditemukan, lakukan fallback pencarian teks
          pada judul/summary untuk menemukan artikel yang relevan meskipun
          belum diekstrak sebagai simbol.
        """
        # Fetch a larger, older pool for symbol-specific matching
        all_news = self.fetch_news(limit=DEFAULT_TOTAL_FETCH_LIMIT, max_age_days=DEFAULT_SYMBOL_MAX_AGE_DAYS, max_per_feed_override=DEFAULT_MAX_PER_FEED * 2)

        # Re-extract symbols dengan known_tickers context agar artikel yang
        # menyebut perusahaan di luar watchlist default bisa terdeteksi
        # (contoh: "Bayan Resources" akan match BAYAN.JK kalau user query BAYAN)

        # ── Resolve simbol dari query user ───────────────────────────────────
        # Bisa berupa: ticker (BAYAN / BAYAN.JK), nama perusahaan, atau keyword
        candidates = set()
        sym_up = symbol.upper().replace(".JK", "")
        full_ticker = f"{sym_up}.JK"
        lower = symbol.lower()

        # 1. Jika input adalah ticker eksplisit → langsung pakai
        if symbol.upper().endswith('.JK') or full_ticker in self._get_all_symbols():
            candidates.add(full_ticker)

        # 2. Cek di COMPANY_TO_SYMBOL (dikurasi)
        if lower in COMPANY_TO_SYMBOL:
            candidates.add(COMPANY_TO_SYMBOL[lower])

        # 3. Cek dynamic ALL_SYMBOLS — exact name match ATAU ticker match
        try:
            for s, name in self._get_all_symbols().items():
                if not name:
                    continue
                # Exact ticker match (misal user ketik "BAYAN")
                if s.replace(".JK","").upper() == sym_up:
                    candidates.add(s)
                # Exact full name match
                elif name.lower() == lower:
                    candidates.add(s)
        except Exception:
            pass

        # Jika tidak ketemu sama sekali, gunakan input apa adanya sebagai fallback
        if not candidates:
            candidates.add(full_ticker)

        logger.info(f"Symbol query '{symbol}' → candidates: {candidates}")

        # Build a set of loose name tokens (company short names, first words,
        # and component words) derived from candidates so we can do
        # substring-based fallback matching (more permissive).
        name_tokens = set()
        try:
            # From tickers available in ALL_SYMBOLS, add human-readable names
            for c in list(candidates):
                if c in self._get_all_symbols():
                    name = self._get_all_symbols().get(c)
                    if name:
                        nl = name.lower()
                        name_tokens.add(nl)
                        # add first word alias
                        first = nl.split()[0]
                        name_tokens.add(first)
                        # add component words
                        for w in re.split(r"[^a-z0-9]+", nl):
                            if len(w) > 3:
                                name_tokens.add(w)
        except Exception:
            pass

        # Hanya panggil yfinance jika simbol BELUM ditemukan di curated maps
        # (menghindari 404 error untuk "astra", "mandiri", dll yang sudah diketahui)
        _already_resolved = bool(candidates)
        if not _already_resolved:
         try:
            from ..services.data_service import DataService
            ds = DataService()
            # 1) Yahoo search untuk ticker yang benar-benar tidak diketahui
            try:
                search_results = ds.search_tickers(symbol)
                for r in search_results:
                    symr = r.get('symbol')
                    nm = r.get('name')
                    exch = (r.get('exchange') or '').lower()
                    if not symr:
                        continue
                    if symr.endswith('.JK') or 'idx' in exch or 'jkt' in exch:
                        candidates.add(symr)
                        if nm:
                            nl = nm.lower()
                            name_tokens.add(nl)
                            first = nl.split()[0] if nl else ''
                            if len(first) > 3:
                                name_tokens.add(first)
            except Exception:
                pass

            # 2) get_symbol_info sebagai fallback
            lookup_symbols = [symbol, symbol.upper() + (".JK" if not symbol.upper().endswith('.JK') else "")]
            for ls in lookup_symbols:
                try:
                    info = ds.get_symbol_info(ls)
                except Exception:
                    info = {}
                name = info.get('name') if isinstance(info, dict) else None
                if name and name.lower() != symbol.lower():
                    nl = name.lower()
                    name_tokens.add(nl)
                    first = nl.split()[0]
                    if first and len(first) > 3:
                        name_tokens.add(first)
                    break
         except Exception:
            pass

        # Also add the short company alias (first word) into candidates so
        # ticker-based queries (e.g. 'ASII') will match articles that use the
        # company short name (e.g. 'Astra') in title/summary.
        try:
            for c in list(candidates):
                if c in self._get_all_symbols():
                    name = self._get_all_symbols().get(c)
                    if name:
                        first = name.split()[0].lower()
                        # add alias to name_tokens, not candidates
                        name_tokens.add(first)
        except Exception:
            pass

        # If a candidate ticker maps from COMPANY_TO_SYMBOL (value), also add
        # the keyword names from COMPANY_TO_SYMBOL (keys) so ticker queries
        # like 'ASII' will also match text that uses simpler keywords like
        # 'astra'.
        try:
            for nm, sym in COMPANY_TO_SYMBOL.items():
                if sym in candidates:
                    # map keyword names into name_tokens (looser matching)
                    name_tokens.add(nm)
        except Exception:
            pass

        # From COMPANY_TO_SYMBOL mapping: if mapping points to one of our
        # candidate tickers, include the keyword names (and their words).
        # Tandai juga sebagai "curated_tokens" — token ini aman tanpa financial keyword
        curated_tokens = set()
        for nm, sym in COMPANY_TO_SYMBOL.items():
            if sym in candidates:
                nn = nm.lower()
                name_tokens.add(nn)
                curated_tokens.add(nn)  # token ini sudah dikurasi, aman
                for w in re.split(r"[^a-z0-9]+", nn):
                    if len(w) > 3:
                        name_tokens.add(w)
                        curated_tokens.add(w)

        def _has_financial_keyword(text: str) -> bool:
            try:
                for kw in FINANCIAL_KEYWORDS:
                    try:
                        if re.search(r"\b" + re.escape(kw) + r"\b", text):
                            return True
                    except Exception:
                        continue
            except Exception:
                return False
            return False

        def _article_matches(article: NewsArticle, candidate_set: set) -> bool:
            # 1) already categorized with extracted symbols
            if any(c in article.symbols for c in candidate_set):
                return True

            # 2) fallback: plain-text search in title+summary for symbol/company tokens
            text = f"{article.title} {article.summary}".lower()
            title = article.title or ""
            summary = article.summary or ""
            for c in candidate_set:
                token = c.lower().replace('.jk', '')
                token_upper = token.upper()
                # Accept explicit ticker mentions in TITLE/SUMMARY (often
                # presented as uppercase) OR token + financial keyword in body
                try:
                    if re.search(r"\b" + re.escape(token_upper) + r"(\\.JK)?\b", title) or re.search(r"\b" + re.escape(token_upper) + r"(\\.JK)?\b", summary):
                        return True
                except Exception:
                    pass
                if re.search(r"\b" + re.escape(token) + r"\b", text) and _has_financial_keyword(text):
                    return True

            # 3) check Company name mapping explicitly (e.g. 'bank mandiri' → BMRI.JK)
            for name, sym in COMPANY_TO_SYMBOL.items():
                if sym in candidate_set:
                    if re.search(r"\b" + re.escape(name.lower()) + r"\b", text):
                        return True

            # 4) check ALL_SYMBOLS human-readable names
            try:
                for s, name in self._get_all_symbols().items():
                    if s in candidate_set and name:
                        # match full company name explicitly (strong signal)
                        nl = name.lower()
                        if re.search(r"\b" + re.escape(nl) + r"\b", text):
                            return True
                        # For the first-word alias (short name), require financial
                        # context to avoid matching generic place names (e.g. 'Bayan')
                        first = nl.split()[0]
                        if first and re.search(r"\b" + re.escape(first) + r"\b", text):
                            if _has_financial_keyword(text):
                                return True
            except Exception:
                pass

            # 5) permissive substring match against name tokens (looser)
            try:
                title_text = article.title.lower()
                for token in name_tokens:
                    if not token:
                        continue
                    tl = token.lower()
                    # Untuk curated_tokens (dari COMPANY_TO_SYMBOL) → tidak perlu
                    # financial keyword karena sudah pasti merujuk ke perusahaan IDX
                    is_curated = tl in curated_tokens
                    if tl in title_text:
                        if is_curated:
                            return True  # langsung accept: "Astra" di judul = berita Astra
                        try:
                            is_ticker_token = any(tok.lower().replace('.jk','') == tl for tok in candidate_set)
                        except Exception:
                            is_ticker_token = False
                        if is_ticker_token or _has_financial_keyword(text):
                            return True
                    # accept if token appears in body
                    if tl in text:
                        if is_curated or _has_financial_keyword(text):
                            return True
            except Exception:
                pass

            return False

        # Filter candidate articles
        filtered = [a for a in all_news if _article_matches(a, candidates)]

        # If we have fewer than a reasonable minimum, attempt looser matching
        min_needed = 5
        if len(filtered) < min_needed:
            needed = min_needed - len(filtered)
            extras = []
            existing_ids = {a.id for a in filtered}
            for article in all_news:
                if article.id in existing_ids:
                    continue
                text = f"{article.title} {article.summary}".lower()
                title_text = article.title.lower()
                added = False
                for c in candidates:
                    token = c.lower().replace('.jk', '')
                    # require token in title OR token in body with financial keyword context
                    if token in title_text or (token in text and _has_financial_keyword(text)):
                        extras.append(article)
                        existing_ids.add(article.id)
                        added = True
                        break
                if added:
                    if len(extras) >= needed:
                        break
                    else:
                        continue
                # also try looser name token substring matching but require
                # explicit financial context to avoid generic place-name hits
                if len(extras) < needed:
                    for nt in name_tokens:
                        if not nt:
                            continue
                        # require at least one financial keyword in the article
                        # when matching by loose name tokens (title or body)
                        if (nt in title_text or nt in text) and _has_financial_keyword(text):
                            extras.append(article)
                            existing_ids.add(article.id)
                            break
                if len(extras) >= needed:
                    break
            if extras:
                filtered.extend(extras)

        # If still not enough results, try a Google News RSS fallback for the symbol
        # but only when we have at least one credible .JK ticker candidate to
        # avoid noisy geographic/place matches for ambiguous short tokens.
        if len(filtered) < min_needed:
            try:
                # treat any .JK candidate as potentially credible (we may have
                # discovered it via Yahoo search earlier), don't require it to be
                # already present in the local IHSG cache
                credible_tickers = [c for c in candidates if c.endswith('.JK')]
                if not credible_tickers:
                    # skip Google fallback when no credible ticker candidate
                    raise RuntimeError('No credible ticker candidate; skipping Google fallback')
                # Build a list of Google search queries to bias toward financial
                # results. Prefer full company names (if available) and include
                # variants like 'saham' or 'tbk' to avoid generic-language hits.
                google_queries = []
                # try the raw symbol first and add finance-biased variants
                google_queries.append(symbol)
                google_queries.append(f"{symbol} saham")
                google_queries.append(f"{symbol} tbk")
                # include any discovered full names (from name_tokens that look like full names)
                full_names = [n for n in name_tokens if ' ' in n]
                # also include candidate names from ALL_SYMBOLS that match our candidates
                try:
                    for c in list(candidates):
                        if c in self._get_all_symbols():
                            nm = self._get_all_symbols().get(c)
                            if nm:
                                full_names.append(nm.lower())
                except Exception:
                    pass

                # dedupe and build queries with financial context
                seen_q = set()
                for fn in full_names:
                    if not fn:
                        continue
                    q1 = fn
                    q2 = f'"{fn}"'
                    q3 = f'"{fn}" saham'
                    q4 = f'"{fn}" tbk'
                    for qcand in (q1, q2, q3, q4):
                        if qcand not in seen_q:
                            google_queries.append(qcand)
                            seen_q.add(qcand)

                existing_ids = {a.id for a in filtered}
                for gq in google_queries[:6]:
                    pass  # Menutup loop for yang terpotong

            except Exception:
                pass  # Menutup blok try dari baris 680

        # Filter ketat: hanya artikel yang punya simbol relevan atau keyword finansial
        def _is_financially_relevant(article) -> bool:
            text = f"{article.title} {article.summary}".lower()
            # Kalau sudah ada simbol yang di-extract, langsung lolos
            if article.symbols:
                return True
            # Wajib ada minimal satu financial keyword
            return _has_financial_keyword(text)

        filtered = [a for a in filtered if _is_financially_relevant(a)]

        # Sort dan batasi hasil
        try:
            cutoff = datetime.now() - timedelta(days=DEFAULT_SYMBOL_MAX_AGE_DAYS)
            filtered = [a for a in filtered if a.published_at >= cutoff]
        except Exception:
            pass

        # If still not enough symbol-specific articles, try ticker-specific
        # news from Yahoo (via DataService.get_news_for_symbol) as a last resort.
        try:
            if len(filtered) < min_needed:
                from ..services.data_service import DataService
                ds = DataService()
                existing_ids = {a.id for a in filtered}
                # iterate over explicit ticker candidates first
                tickers_to_try = [c for c in candidates if c.endswith('.JK')]
                # also try candidates without suffix
                tickers_to_try.extend([f"{c}.JK" for c in candidates if not c.endswith('.JK')])
                for t in tickers_to_try:
                    if len(filtered) >= min_needed:
                        break
                    try:
                        extra = ds.get_news_for_symbol(t, count=10)
                    except Exception:
                        extra = []
                    for e in extra:
                        if e.id in existing_ids:
                            continue
                        if _article_matches(e, candidates):
                            filtered.append(e)
                            existing_ids.add(e.id)
                        if len(filtered) >= min_needed:
                            break
        except Exception:
            pass

        filtered.sort(key=lambda x: x.published_at, reverse=True)

        # Post-filter: remove articles that only match a loose name token
        # but contain no explicit financial context or full-company name.
        # This avoids returning geographic/place articles when the only
        # signal is a short shared word (e.g. 'Bayan').
        try:
            full_names = [n for n in name_tokens if ' ' in n]
        except Exception:
            full_names = []

        pruned = []
        for a in filtered:
            try:
                text = f"{a.title} {a.summary}".lower()
            except Exception:
                text = ""
            if not a.symbols:
                has_fin = _has_financial_keyword(text)
                has_name = any(nt in text for nt in name_tokens)
                has_full_name = any(fn in text for fn in full_names)
                if has_name and not has_fin and not has_full_name:
                    # skip overly-loose match
                    continue
            pruned.append(a)

        filtered = pruned
        result = filtered[:limit]

        # If nothing found, and the query looks like a ticker, try searching
        # by the company's short name (e.g. 'ASII' -> 'astra') as a fallback.
        if not result:
            try:
                seek = sym_up if 'sym_up' in locals() else symbol.upper()
                # Find matching ALL_SYMBOLS key by ticker
                for s, name in self._get_all_symbols().items():
                    if s.replace('.JK', '').upper() == seek.replace('.JK','').upper():
                        short = name.split()[0].lower()
                        if short and short.lower() != symbol.lower():
                            # Recursively search by short name (this will apply
                            # the same matching logic but with the company keyword)
                            return self.fetch_news_by_symbol(short, limit=limit, compute_sentiment=compute_sentiment)
            except Exception:
                pass

        # Optionally compute sentiment per-article for filtered results.
        if compute_sentiment and result:
            try:
                from .. import main as app_main
                sentiment_agent = getattr(app_main, "sentiment_agent", None)
            except Exception:
                sentiment_agent = None

            if sentiment_agent:
                for article in result:
                    try:
                        analysis = sentiment_agent._aggregate_article_sentiment(article)
                        article.sentiment_score = analysis.get("score", 0.0)
                    except Exception:
                        continue

        return result

        # If still not enough symbol-specific articles, try ticker-specific
        # news from Yahoo (via DataService.get_news_for_symbol) as a last resort.
        try:
            from ..services.data_service import DataService
            ds = DataService()
            existing_ids = {a.id for a in filtered}
            # iterate over explicit ticker candidates first
            tickers_to_try = [c for c in candidates if c.endswith('.JK')]
            # also try candidates without suffix
            tickers_to_try.extend([f"{c}.JK" for c in candidates if not c.endswith('.JK')])
            for t in tickers_to_try:
                if len(filtered) >= min_needed:
                    break
                try:
                    extra = ds.get_news_for_symbol(t, count=10)
                except Exception:
                    extra = []
                for e in extra:
                    if e.id in existing_ids:
                        continue
                    if _article_matches(e, candidates):
                        filtered.append(e)
                        existing_ids.add(e.id)
                    if len(filtered) >= min_needed:
                        break
        except Exception:
            pass

    def get_latest_headlines(self, limit: int = 10) -> List[dict]:
        """Ambil headline terbaru dalam format sederhana untuk dashboard.
        Hanya berita finansial yang sudah melewati filter _parse_feed.
        sentiment_score dihitung oleh SentimentAgent jika model sudah siap.
        """
        articles = self.fetch_news(limit=limit, compute_sentiment=True)
        return [
            {
                "title": a.title,
                "source": a.source,
                "url": a.url,
                "published_at": a.published_at.isoformat(),
                "symbols": a.symbols,
                "sentiment_score": a.sentiment_score,
            }
            for a in articles
        ]

    def invalidate_cache(self):
        """Force refresh cache berita."""
        self._cache = None
        self._cache_time = None
