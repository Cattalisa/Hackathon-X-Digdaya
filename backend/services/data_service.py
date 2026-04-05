"""
NusaTerminal - Data Service
Mengambil data pasar real-time dan historis via yfinance.
Dilengkapi TTL cache agar tidak spam request ke Yahoo Finance.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional
import cachetools
import logging

from ..models.schemas import MarketData, MarketType

logger = logging.getLogger(__name__)


# ─── DAFTAR ASET ──────────────────────────────────────────────────────────────

INDONESIAN_STOCKS: Dict[str, str] = {
    "BBCA.JK":  "Bank Central Asia",
    "BBRI.JK":  "Bank Rakyat Indonesia",
    "BMRI.JK":  "Bank Mandiri",
    "BBNI.JK":  "Bank Negara Indonesia",
    "TLKM.JK":  "Telkom Indonesia",
    "ASII.JK":  "Astra International",
    "UNVR.JK":  "Unilever Indonesia",
    "ICBP.JK":  "Indofood CBP",
    "INDF.JK":  "Indofood Sukses Makmur",
    "ANTM.JK":  "Aneka Tambang",
    "PTBA.JK":  "Bukit Asam",
    "ADRO.JK":  "Adaro Energy",
    "KLBF.JK":  "Kalbe Farma",
    "GOTO.JK":  "GoTo Gojek Tokopedia",
}

COMMODITIES: Dict[str, str] = {
    "GC=F":     "Emas (Gold Futures)",
    "CL=F":     "Minyak Mentah (Crude Oil)",
    "FCPO.BMD": "CPO (Crude Palm Oil)",  # BMD Malaysia sebagai proxy
}

INDICES: Dict[str, str] = {
    "^JKSE":    "IHSG (Jakarta Composite)",
    "^KLSE":    "KLCI (Kuala Lumpur)",
}

ALL_SYMBOLS = {**INDONESIAN_STOCKS, **COMMODITIES, **INDICES}


class DataService:
    """
    Service layer untuk mengambil data pasar dari Yahoo Finance.
    Cache TTL 60 detik untuk data real-time, 5 menit untuk summary.
    """

    def __init__(self):
        # Cache untuk data real-time (60 detik)
        self._realtime_cache = cachetools.TTLCache(maxsize=200, ttl=60)
        # Cache untuk market summary (5 menit)
        self._summary_cache = cachetools.TTLCache(maxsize=10, ttl=300)

    def _get_market_type(self, symbol: str) -> MarketType:
        if symbol in COMMODITIES:
            return MarketType.COMMODITY
        elif symbol in INDICES:
            return MarketType.INDEX
        return MarketType.STOCK

    def _fetch_single(self, symbol: str) -> Optional[MarketData]:
        """Fetch data satu simbol dari yfinance."""
        # Cek cache dulu
        cached = self._realtime_cache.get(symbol)
        if cached:
            return cached

        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="2d", interval="1m")

            if hist.empty:
                logger.warning(f"Tidak ada data untuk {symbol}")
                return None

            latest = hist.iloc[-1]
            # Prev close: ambil dari hari sebelumnya jika ada
            prev_close = hist[hist.index.date < hist.index[-1].date()]["Close"]
            prev_close_val = prev_close.iloc[-1] if not prev_close.empty else latest["Close"]

            change = float(latest["Close"]) - float(prev_close_val)
            change_pct = (change / float(prev_close_val)) * 100 if prev_close_val != 0 else 0.0

            # Use the timestamp from the OHLCV row for last_update (more accurate)
            last_ts = None
            try:
                last_ts = getattr(latest, 'name', None)
                if hasattr(last_ts, 'to_pydatetime'):
                    last_ts = last_ts.to_pydatetime()
            except Exception:
                last_ts = None

            data = MarketData(
                symbol=symbol,
                name=ALL_SYMBOLS.get(symbol, symbol),
                price=round(float(latest["Close"]), 2),
                change=round(change, 2),
                change_percent=round(change_pct, 4),
                volume=int(latest["Volume"]),
                open=round(float(latest["Open"]), 2),
                high=round(float(latest["High"]), 2),
                low=round(float(latest["Low"]), 2),
                close=round(float(latest["Close"]), 2),
                last_update=last_ts or datetime.now(),
                market_type=self._get_market_type(symbol),
            )

            self._realtime_cache[symbol] = data
            return data

        except Exception as e:
            logger.error(f"Error fetch {symbol}: {e}")
            return None

    def _make_fallback(self, symbol: str) -> MarketData:
        """Buat data kosong jika fetch gagal — agar UI tidak crash."""
        return MarketData(
            symbol=symbol,
            name=ALL_SYMBOLS.get(symbol, symbol),
            price=0.0, change=0.0, change_percent=0.0,
            volume=0, open=0.0, high=0.0, low=0.0, close=0.0,
            last_update=datetime.now(),
            market_type=self._get_market_type(symbol),
        )

    def _fetch_batch(self, symbols: List[str]) -> Dict[str, Optional[MarketData]]:
        """Batch fetch menggunakan yf.download sehingga timestamps konsisten bila memungkinkan."""
        results: Dict[str, Optional[MarketData]] = {s: None for s in symbols}

        try:
            # yf.download supports multiple tickers; request grouped by ticker
            df = yf.download(tickers=symbols, period="2d", interval="1m", group_by='ticker', threads=True, progress=False)
        except Exception as e:
            logger.warning(f"Batch download gagal: {e}. Falling back to single fetch.")
            for s in symbols:
                results[s] = self._fetch_single(s)
            return results

        for s in symbols:
            try:
                # Try to access per-ticker dataframe when group_by='ticker' worked
                if s in df.columns:
                    tdf = df[s]
                else:
                    # Fallback: try to get columns like ('Close', s)
                    if isinstance(df.columns, pd.MultiIndex) and 'Close' in df.columns.levels[0]:
                        if s in df['Close'].columns:
                            tdf = df.xs(s, axis=1, level=1)
                        else:
                            tdf = df
                    else:
                        tdf = df

                if 'Close' not in tdf.columns:
                    # No usable data
                    results[s] = None
                    continue

                tdf = tdf.dropna(subset=['Close'])
                if tdf.empty:
                    results[s] = None
                    continue

                latest = tdf.iloc[-1]
                last_ts = None
                try:
                    last_ts = getattr(latest, 'name', None)
                    if hasattr(last_ts, 'to_pydatetime'):
                        last_ts = last_ts.to_pydatetime()
                except Exception:
                    last_ts = None

                prev_close = tdf[tdf.index.date < tdf.index[-1].date()]['Close']
                prev_close_val = prev_close.iloc[-1] if not prev_close.empty else latest['Close']

                change = float(latest['Close']) - float(prev_close_val)
                change_pct = (change / float(prev_close_val)) * 100 if prev_close_val != 0 else 0.0

                data = MarketData(
                    symbol=s,
                    name=ALL_SYMBOLS.get(s, s),
                    price=round(float(latest['Close']), 2),
                    change=round(change, 2),
                    change_percent=round(change_pct, 4),
                    volume=int(latest.get('Volume', 0)),
                    open=round(float(latest.get('Open', 0.0)), 2),
                    high=round(float(latest.get('High', 0.0)), 2),
                    low=round(float(latest.get('Low', 0.0)), 2),
                    close=round(float(latest['Close']), 2),
                    last_update=last_ts or datetime.now(),
                    market_type=self._get_market_type(s),
                )

                self._realtime_cache[s] = data
                results[s] = data

            except Exception as e:
                logger.debug(f"_fetch_batch: fallback single for {s}: {e}")
                results[s] = self._fetch_single(s)

        return results

    # ── Public API ────────────────────────────────────────────────────────────

    def get_market_data(self, symbols: Optional[List[str]] = None) -> List[MarketData]:
        """
        Ambil data real-time untuk list simbol.
        Jika symbols=None, ambil semua saham IDX dalam watchlist.
        """
        if symbols is None:
            symbols = list(INDONESIAN_STOCKS.keys())

        # Use batch fetch for multiple symbols to improve timestamp alignment
        if symbols and len(symbols) > 1:
            batch = self._fetch_batch(symbols)
            return [batch.get(s) if batch.get(s) else self._make_fallback(s) for s in symbols]

        # Single-symbol path
        results = []
        for symbol in symbols:
            data = self._fetch_single(symbol)
            results.append(data if data else self._make_fallback(symbol))

        return results

    def get_all_assets(self) -> List[MarketData]:
        """Ambil semua aset: saham IDX + komoditas + indeks."""
        all_syms = list(INDONESIAN_STOCKS.keys()) + list(COMMODITIES.keys()) + list(INDICES.keys())
        return self.get_market_data(all_syms)

    def get_historical_data(self, symbol: str, period: str = "3mo") -> pd.DataFrame:
        """
        Ambil data historis OHLCV untuk kalkulasi indikator teknikal.
        period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y
        """
        cache_key = f"hist_{symbol}_{period}"
        cached = self._realtime_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)

            if not hist.empty:
                self._realtime_cache[cache_key] = hist

            return hist

        except Exception as e:
            logger.error(f"Error fetch historis {symbol}: {e}")
            return pd.DataFrame()

    def get_market_summary(self) -> Dict[str, Any]:
        """Ambil ringkasan IHSG + statistik pasar."""
        cached = self._summary_cache.get("ihsg_summary")
        if cached:
            return cached

        try:
            ihsg = yf.Ticker("^JKSE")
            hist = ihsg.history(period="5d")

            if not hist.empty:
                latest = hist.iloc[-1]
                prev = hist.iloc[-2] if len(hist) > 1 else latest

                summary = {
                    "index": "IHSG",
                    "price": round(float(latest["Close"]), 2),
                    "change": round(float(latest["Close"]) - float(prev["Close"]), 2),
                    "change_percent": round(
                        ((float(latest["Close"]) - float(prev["Close"])) / float(prev["Close"])) * 100, 4
                    ),
                    "volume": int(latest["Volume"]),
                    "high": round(float(latest["High"]), 2),
                    "low": round(float(latest["Low"]), 2),
                    "timestamp": datetime.now().isoformat(),
                }

                self._summary_cache["ihsg_summary"] = summary
                return summary

        except Exception as e:
            logger.error(f"Error fetch IHSG: {e}")

        return {
            "index": "IHSG", "price": 0, "change": 0,
            "change_percent": 0, "volume": 0,
            "timestamp": datetime.now().isoformat(),
        }

    def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """Ambil informasi fundamental saham (nama, sektor, market cap, dll)."""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            return {
                "symbol": symbol,
                "name": info.get("longName", ALL_SYMBOLS.get(symbol, symbol)),
                "sector": info.get("sector", "N/A"),
                "industry": info.get("industry", "N/A"),
                "market_cap": info.get("marketCap", 0),
                "pe_ratio": info.get("trailingPE", None),
                "pb_ratio": info.get("priceToBook", None),
                "dividend_yield": info.get("dividendYield", None),
                "52w_high": info.get("fiftyTwoWeekHigh", None),
                "52w_low": info.get("fiftyTwoWeekLow", None),
                "description": info.get("longBusinessSummary", "")[:300],
            }
        except Exception as e:
            logger.error(f"Error fetch info {symbol}: {e}")
            return {"symbol": symbol, "name": ALL_SYMBOLS.get(symbol, symbol)}

    def get_ihsg_constituents(self, refresh: bool = False) -> Dict[str, str]:
        import os
        import json
        import time

        cache_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.abspath(os.path.join(cache_dir, 'ihsg_constituents.json'))

        # try cache
        try:
            if os.path.exists(cache_file) and not refresh:
                mtime = os.path.getmtime(cache_file)
                if (time.time() - mtime) < 24 * 3600:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
        except Exception:
            pass

        constituents: Dict[str, str] = {}

        # Try a more robust IDX API scrape with varied headers before other fallbacks
        try:
            idx_scraped = self._scrape_idx_api()
            if idx_scraped:
                try:
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        json.dump(idx_scraped, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass
                return idx_scraped
        except Exception:
            pass

        # Attempt IDX endpoints (simple HTTP GET + JSON parse)
        idx_urls = [
            'https://www.idx.co.id/umbraco/Surface/ListedCompany/GetListedCompanyByCriteria?keyword=&page=1&size=2000',
            'https://www.idx.co.id/umbraco/Api/Company/GetListedCompanies?keyword=&page=1&size=2000',
            'https://www.idx.co.id/umbraco/Surface/ListedCompany/GetListedCompany?page=1&size=2000',
        ]
        for url in idx_urls:
            try:
                import urllib.request
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    text = resp.read().decode('utf-8', errors='ignore')
                try:
                    data = json.loads(text)
                except Exception:
                    data = None

                items = None
                if isinstance(data, dict):
                    for k in ('data', 'rows', 'result', 'results', 'items', 'companies'):
                        if k in data and isinstance(data[k], list):
                            items = data[k]
                            break
                elif isinstance(data, list):
                    items = data

                if not items:
                    # try to find a JSON array inside the HTML
                    import re
                    m = re.search(r"\[\{.+\}\]", text, flags=re.S)
                    if m:
                        try:
                            items = json.loads(m.group(0))
                        except Exception:
                            items = None

                if items and isinstance(items, list):
                    for it in items:
                        if not isinstance(it, dict):
                            continue
                        keys = {k.lower(): v for k, v in it.items()}
                        sym = None
                        name = None
                        for k in ('kodeemiten', 'kode', 'symbol', 'code', 'ticker', 'emitencode'):
                            if k in keys and keys[k]:
                                sym = str(keys[k]).strip()
                                break
                        for k in ('namaperusahaan', 'companyname', 'company', 'name', 'longname', 'shortname'):
                            if k in keys and keys[k]:
                                name = str(keys[k]).strip()
                                break
                        if sym:
                            su = sym.upper()
                            if not su.endswith('.JK'):
                                su = su + '.JK'
                            constituents[su] = name or su
                    if constituents:
                        try:
                            with open(cache_file, 'w', encoding='utf-8') as f:
                                json.dump(constituents, f, ensure_ascii=False, indent=2)
                        except Exception:
                            pass
                        return constituents
            except Exception:
                continue

        # Fallback: use Yahoo search to discover JKT symbols (A-Z)
        letters = [chr(i) for i in range(ord('A'), ord('Z') + 1)]
        seen = set()
        for q in letters:
            try:
                res = self.search_tickers(q, count=80)
            except Exception:
                res = []
            for r in res:
                sym = r.get('symbol')
                name = r.get('name')
                exch = (r.get('exchange') or '').lower()
                if not sym:
                    continue
                su = str(sym).upper()
                if not su.endswith('.JK') and ('jkt' in exch or (name and 'tbk' in name.lower())):
                    su = su + '.JK'
                if su.endswith('.JK') or (name and 'tbk' in name.lower()):
                    if su not in seen:
                        constituents[su] = name or su
                        seen.add(su)
            try:
                time.sleep(0.2)
            except Exception:
                pass

        # If still small, try sector/keyword-based queries which often return many TBK/JKT results
        if len(constituents) < 300:
            sector_queries = [
                'tbk', 'pt', 'indonesia', 'jkt', 'bank', 'property', 'energy', 'mining',
                'resources', 'telecom', 'agro', 'food', 'cement', 'coal', 'metal', 'insurance', 'finance'
            ]
            for q in sector_queries:
                try:
                    res = self.search_tickers(q, count=200)
                except Exception:
                    res = []
                for r in res:
                    sym = r.get('symbol')
                    name = r.get('name')
                    exch = (r.get('exchange') or '').lower()
                    if not sym:
                        continue
                    su = str(sym).upper()
                    if not su.endswith('.JK') and ('jkt' in exch or (name and 'tbk' in name.lower())):
                        su = su + '.JK'
                    if su.endswith('.JK') or (name and 'tbk' in name.lower()):
                        if su not in seen:
                            constituents[su] = name or su
                            seen.add(su)
                try:
                    time.sleep(0.2)
                except Exception:
                    pass

        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(constituents, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        # Additional fallback: try Wikipedia category discovery to fill gaps
        try:
            if len(constituents) < 500:
                wiki_found = self._discover_from_wikipedia()
                for s, n in wiki_found.items():
                    if s not in constituents:
                        constituents[s] = n
        except Exception:
            pass

        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(constituents, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        return constituents

    def _discover_from_wikipedia(self) -> Dict[str, str]:
        """Attempt to discover IDX-listed company names via Wikipedia category pages.

        This method scrapes the "Category:Companies listed on the Indonesia Stock Exchange"
        page and uses `search_tickers` to map company page names to .JK tickers where
        possible. This is an additional fallback when IDX API and Yahoo discovery
        return too few results.
        """
        try:
            import urllib.request
            import re
            import time

            url = 'https://en.wikipedia.org/wiki/Category:Companies_listed_on_the_Indonesia_Stock_Exchange'
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                text = resp.read().decode('utf-8', errors='ignore')

            # Extract links from the category listing (anchor href + link text)
            # Narrow to the mw-category block to avoid unrelated navigation links
            cat_idx = text.find('class="mw-category"')
            block = text[cat_idx:cat_idx+20000] if cat_idx != -1 else text
            # match anchors to company pages; exclude links containing ':' (Category:, File:, etc.)
            entries = re.findall(r'<a href="(/wiki/([^"]+))"[^>]*>([^<]+)</a>', block)
            results: Dict[str, str] = {}
            seen = set()

            for full, path, display in entries:
                # skip names that are category/file/portal links
                if ':' in path:
                    continue
                company = display.strip()
                if not company:
                    continue
                # Use Yahoo search to try mapping the company name to a ticker
                try:
                    candidates = self.search_tickers(company, count=10)
                except Exception:
                    candidates = []

                for c in candidates:
                    sym = c.get('symbol')
                    name = c.get('name') or company
                    exch = (c.get('exchange') or '').lower() or ''
                    if not sym:
                        continue
                    su = str(sym).upper()
                    if not su.endswith('.JK') and ('jkt' in exch or 'idx' in exch or (name and 'tbk' in name.lower())):
                        su = su + '.JK'
                    if su.endswith('.JK') or (name and 'tbk' in name.lower()):
                        if su not in seen:
                            results[su] = name or company
                            seen.add(su)

                try:
                    time.sleep(0.08)
                except Exception:
                    pass

            return results
        except Exception:
            return {}

    def _scrape_idx_api(self) -> Dict[str, str]:
        """Try multiple IDX endpoints with varied headers and parse JSON/HTML.

        Returns a mapping symbol->name when successful, or empty dict.
        """
        try:
            import urllib.request
            import json
            import re
            import time
            from html import unescape

            # Broader list of possible IDX endpoints / pages (include language variants and larger sizes)
            idx_urls = [
                'https://www.idx.co.id/umbraco/Surface/ListedCompany/GetListedCompanyByCriteria?keyword=&page=1&size=5000',
                'https://www.idx.co.id/umbraco/Api/Company/GetListedCompanies?keyword=&page=1&size=5000',
                'https://www.idx.co.id/umbraco/Surface/ListedCompany/GetListedCompany?page=1&size=5000',
                'https://www.idx.co.id/umbraco/Api/Company/GetListedCompanies?keyword=&page=1&size=10000',
                'https://www.idx.co.id/umbraco/Surface/ListedCompany/GetListedCompanyByCriteria?keyword=&page=1&size=10000',
                'https://www.idx.co.id/umbraco/Surface/ListedCompany/GetListedCompany?page=1&size=10000',
                'https://www.idx.co.id/umbraco/api/Company/GetListedCompanies?keyword=&page=1&size=10000',
                'https://www.idx.co.id/en-us/listed-companies/',
                'https://www.idx.co.id/id/beranda/perusahaan-tercatat',
                'https://www.idx.co.id/daftar-perusahaan-tercatat',
                'https://www.idx.co.id/perusahaan-tercatat',
                'https://www.idx.co.id/en-us/listed-companies/?page=1',
            ]

            # Rotate several realistic header variants including language hints
            header_variants = [
                {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "application/json, text/javascript, */*; q=0.01", "X-Requested-With": "XMLHttpRequest", "Referer": "https://www.idx.co.id/", "Accept-Language": "id-ID,en-US;q=0.9", "Connection": "keep-alive"},
                {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", "Accept": "application/json", "Accept-Language": "en-US,en;q=0.9", "Connection": "keep-alive"},
                {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "text/html", "Accept-Language": "id-ID", "Connection": "keep-alive"},
            ]

            tried = set()
            for url in idx_urls:
                for headers in header_variants:
                    for method in ("GET", "POST"):
                        # avoid repeating identical attempts
                        key = f"{url}|{headers.get('User-Agent','')[:40]}|{method}"
                        if key in tried:
                            continue
                        tried.add(key)
                        # Build the request object first; if that fails skip
                        try:
                            if method == "POST":
                                req = urllib.request.Request(url, data=b"", headers=headers)
                            else:
                                req = urllib.request.Request(url, headers=headers)
                        except Exception:
                            continue

                        # Perform the network call in a small try/except to keep scope clear
                        try:
                            with urllib.request.urlopen(req, timeout=12) as resp:
                                text = resp.read().decode('utf-8', errors='ignore')
                        except Exception:
                            continue

                        # 1) Try parse JSON directly
                        data = None
                        try:
                            data = json.loads(text)
                        except Exception:
                            data = None

                        items = None
                        if isinstance(data, dict):
                            # common nested keys
                            for k in ('data', 'rows', 'result', 'results', 'items', 'companies', 'listedCompany'):
                                if k in data and isinstance(data[k], (list, dict)):
                                    if isinstance(data[k], list):
                                        items = data[k]
                                    elif isinstance(data[k], dict):
                                        # try to find a list inside
                                        for kk in ('items', 'companies', 'rows', 'data'):
                                            if kk in data[k] and isinstance(data[k][kk], list):
                                                items = data[k][kk]
                                                break
                                    if items:
                                        break
                        elif isinstance(data, list):
                            items = data

                        constituents: Dict[str, str] = {}
                        if items and isinstance(items, list):
                            for it in items:
                                if not isinstance(it, dict):
                                    continue
                                keys_lower = {k.lower(): v for k, v in it.items()}
                                sym = None
                                name = None
                                for k2 in ('kodeemiten', 'kode', 'symbol', 'code', 'ticker', 'emitencode', 'emiten'):
                                    if k2 in keys_lower and keys_lower[k2]:
                                        sym = str(keys_lower[k2]).strip()
                                        break
                                for k2 in ('namaperusahaan', 'companyname', 'company', 'name', 'longname', 'shortname', 'emitenname'):
                                    if k2 in keys_lower and keys_lower[k2]:
                                        name = str(keys_lower[k2]).strip()
                                        break
                                if sym:
                                    su = re.sub(r'[^A-Z0-9]', '', str(sym).upper())
                                    if not su.endswith('JK'):
                                        su = su + '.JK'
                                    constituents[su] = unescape(name or su)

                            if constituents:
                                return constituents

                        # 2) Try to find JSON array embedded in HTML (broader patterns)
                        if items is None:
                            # look for obvious JSON arrays
                            m = re.search(r'(?P<json>\[\s*\{.*?\}\s*\])', text, flags=re.S)
                            if m:
                                try:
                                    cand = json.loads(m.group('json'))
                                    if isinstance(cand, list):
                                        items = cand
                                except Exception:
                                    items = None

                        # 3) Look for JS-initialized objects (e.g. window.__INITIAL_STATE__ = {...})
                        if items is None:
                            m2 = re.search(r'window\\.__INITIAL_STATE__\\s*=\\s*(\\{.*?\\});', text, flags=re.S)
                            if m2:
                                try:
                                    j = json.loads(m2.group(1))
                                    # find the first list of dicts
                                    for v in j.values():
                                        if isinstance(v, list) and v and isinstance(v[0], dict):
                                            items = v
                                            break
                                except Exception:
                                    items = None

                        if items and isinstance(items, list):
                            for it in items:
                                if not isinstance(it, dict):
                                    continue
                                keys_lower = {k.lower(): v for k, v in it.items()}
                                sym = None
                                name = None
                                for k2 in ('kodeemiten', 'kode', 'symbol', 'code', 'ticker', 'emitencode', 'emiten'):
                                    if k2 in keys_lower and keys_lower[k2]:
                                        sym = str(keys_lower[k2]).strip()
                                        break
                                for k2 in ('namaperusahaan', 'companyname', 'company', 'name', 'longname', 'shortname', 'emitenname'):
                                    if k2 in keys_lower and keys_lower[k2]:
                                        name = str(keys_lower[k2]).strip()
                                        break
                                if sym:
                                    su = re.sub(r'[^A-Z0-9]', '', str(sym).upper())
                                    if not su.endswith('JK'):
                                        su = su + '.JK'
                                    constituents[su] = unescape(name or su)
                            if constituents:
                                return constituents

                        # 4) Fallback: broader HTML table parsing (first two cells)
                        rows = re.findall(r'<tr[^>]*>.*?<td[^>]*>([^<\\n\\r]{1,20})<\\/td>.*?<td[^>]*>([^<\\n\\r]{3,200})<\\/td>', text, flags=re.I|re.S)
                        if rows:
                            for code, name in rows:
                                code_clean = re.sub(r'[^A-Za-z0-9\\.-]', '', code).strip()
                                if not code_clean:
                                    continue
                                su = re.sub(r'[^A-Z0-9]', '', code_clean.upper())
                                if not su.endswith('JK'):
                                    su = su + '.JK'
                                name_clean = re.sub(r'<[^>]*>', '', name).strip()
                                constituents[su] = unescape(name_clean or su)
                            if constituents:
                                return constituents

                        # 5) Anchor/symbol heuristics: search for uppercase tokens that look like tickers
                        tokens = set(re.findall(r'\\b([A-Z]{2,6})\\b', text))
                        for tk in tokens:
                            if len(tk) >= 2 and not tk.isdigit():
                                su = tk.upper()
                                if not su.endswith('JK'):
                                    su = su + '.JK'
                                constituents.setdefault(su, su)
                        if constituents:
                            return constituents

                        # Gentle pause between attempts
                        try:
                            time.sleep(0.12)
                        except Exception:
                            pass

            return {}
        except Exception:
            return {}

    def get_all_symbols(self) -> Dict[str, str]:
        """Return merged mapping of Indonesian stocks + commodities + indices."""
        try:
            ihsg = self.get_ihsg_constituents()
        except Exception:
            ihsg = {**INDONESIAN_STOCKS}

        merged = {**ihsg, **COMMODITIES, **INDICES}
        return merged
        
    def search_tickers(self, query: str, count: int = 20) -> List[Dict[str, Any]]:
        """Search ticker candidates using Yahoo Finance search API.

        Returns a list of dicts with keys: `symbol`, `name`, `exchange`.
        This is used as a fallback when the static `ALL_SYMBOLS` mapping
        does not contain a given query/ticker.
        """
        try:
            import urllib.request
            import urllib.parse
            import json

            q = urllib.parse.quote_plus(query)
            url = f"https://query2.finance.yahoo.com/v1/finance/search?q={q}&quotesCount={count}&newsCount=0"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.load(resp)

            quotes = data.get("quotes", []) or []
            results: List[Dict[str, Any]] = []
            for item in quotes:
                sym = item.get("symbol")
                name = item.get("shortname") or item.get("longname") or item.get("name")
                exch = item.get("exchange") or item.get("exchDisp") or item.get("exchangeTimezoneName")
                if sym:
                    results.append({"symbol": sym, "name": name, "exchange": exch})

            return results
        except Exception as e:
            logger.debug(f"search_tickers failed for {query}: {e}")
            return []

    def get_news_for_symbol(self, symbol: str, count: int = 10) -> List[Any]:
        """Fetch recent news items for a specific ticker using yfinance's ticker.news.

        Returns a list of NewsArticle models when possible; otherwise an empty list.
        """
        try:
            import hashlib
            from datetime import datetime as _dt
            from ..models.schemas import NewsArticle

            ticker = yf.Ticker(symbol)
            news = getattr(ticker, 'news', None) or []
            results = []
            for item in news[:count]:
                try:
                    title = item.get('title') or item.get('headline') or ''
                    link = item.get('link') or item.get('url') or ''
                    pub = item.get('providerPublishTime') or item.get('published')
                    if isinstance(pub, (int, float)):
                        published_at = _dt.fromtimestamp(int(pub))
                    else:
                        published_at = _dt.now()
                    summary = item.get('summary') or item.get('content') or ''
                    source = item.get('publisher') or item.get('providerName') or 'Yahoo'
                    aid = hashlib.md5(f"{symbol}_{link}".encode()).hexdigest()[:16]
                    na = NewsArticle(
                        id=aid,
                        title=title,
                        summary=summary[:500],
                        source=source,
                        url=link,
                        published_at=published_at,
                        symbols=[symbol],
                        sentiment_score=0.0,
                    )
                    results.append(na)
                except Exception:
                    continue
            return results
        except Exception as e:
            logger.debug(f"get_news_for_symbol({symbol}) failed: {e}")
            return []

    # ── Public API ────────────────────────────────────────────────────────────

    def get_market_data(self, symbols: Optional[List[str]] = None) -> List[MarketData]:
        """
        Ambil data real-time untuk list simbol.
        Jika symbols=None, ambil semua saham IDX dalam watchlist.
        """
        if symbols is None:
            symbols = list(INDONESIAN_STOCKS.keys())

        # Use batch fetch for multiple symbols to improve timestamp alignment
        if symbols and len(symbols) > 1:
            batch = self._fetch_batch(symbols)
            return [batch.get(s) if batch.get(s) else self._make_fallback(s) for s in symbols]

        # Single-symbol path
        results = []
        for symbol in symbols:
            data = self._fetch_single(symbol)
            results.append(data if data else self._make_fallback(symbol))

        return results

    def get_all_assets(self) -> List[MarketData]:
        """Ambil semua aset: saham IDX + komoditas + indeks."""
        all_syms = list(INDONESIAN_STOCKS.keys()) + list(COMMODITIES.keys()) + list(INDICES.keys())
        return self.get_market_data(all_syms)

    def get_historical_data(self, symbol: str, period: str = "3mo") -> pd.DataFrame:
        """
        Ambil data historis OHLCV untuk kalkulasi indikator teknikal.
        period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y
        """
        cache_key = f"hist_{symbol}_{period}"
        cached = self._realtime_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)

            if not hist.empty:
                self._realtime_cache[cache_key] = hist

            return hist

        except Exception as e:
            logger.error(f"Error fetch historis {symbol}: {e}")
            return pd.DataFrame()

    def get_market_summary(self) -> Dict[str, Any]:
        """Ambil ringkasan IHSG + statistik pasar."""
        cached = self._summary_cache.get("ihsg_summary")
        if cached:
            return cached

        try:
            ihsg = yf.Ticker("^JKSE")
            hist = ihsg.history(period="5d")

            if not hist.empty:
                latest = hist.iloc[-1]
                prev = hist.iloc[-2] if len(hist) > 1 else latest

                summary = {
                    "index": "IHSG",
                    "price": round(float(latest["Close"]), 2),
                    "change": round(float(latest["Close"]) - float(prev["Close"]), 2),
                    "change_percent": round(
                        ((float(latest["Close"]) - float(prev["Close"])) / float(prev["Close"])) * 100, 4
                    ),
                    "volume": int(latest["Volume"]),
                    "high": round(float(latest["High"]), 2),
                    "low": round(float(latest["Low"]), 2),
                    "timestamp": datetime.now().isoformat(),
                }

                self._summary_cache["ihsg_summary"] = summary
                return summary

        except Exception as e:
            logger.error(f"Error fetch IHSG: {e}")

        return {
            "index": "IHSG", "price": 0, "change": 0,
            "change_percent": 0, "volume": 0,
            "timestamp": datetime.now().isoformat(),
        }

    def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """Ambil informasi fundamental saham (nama, sektor, market cap, dll)."""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            return {
                "symbol": symbol,
                "name": info.get("longName", ALL_SYMBOLS.get(symbol, symbol)),
                "sector": info.get("sector", "N/A"),
                "industry": info.get("industry", "N/A"),
                "market_cap": info.get("marketCap", 0),
                "pe_ratio": info.get("trailingPE", None),
                "pb_ratio": info.get("priceToBook", None),
                "dividend_yield": info.get("dividendYield", None),
                "52w_high": info.get("fiftyTwoWeekHigh", None),
                "52w_low": info.get("fiftyTwoWeekLow", None),
                "description": info.get("longBusinessSummary", "")[:300],
            }
        except Exception as e:
            logger.error(f"Error fetch info {symbol}: {e}")
            return {"symbol": symbol, "name": ALL_SYMBOLS.get(symbol, symbol)}

    def get_ihsg_constituents(self, refresh: bool = False) -> Dict[str, str]:
        import os
        import json
        import time

        cache_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.abspath(os.path.join(cache_dir, 'ihsg_constituents.json'))

        # try cache
        try:
            if os.path.exists(cache_file) and not refresh:
                mtime = os.path.getmtime(cache_file)
                if (time.time() - mtime) < 24 * 3600:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
        except Exception:
            pass

        constituents: Dict[str, str] = {}

        # Try a more robust IDX API scrape with varied headers before other fallbacks
        try:
            idx_scraped = self._scrape_idx_api()
            if idx_scraped:
                try:
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        json.dump(idx_scraped, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass
                return idx_scraped
        except Exception:
            pass

        # Attempt IDX endpoints (simple HTTP GET + JSON parse)
        idx_urls = [
            'https://www.idx.co.id/umbraco/Surface/ListedCompany/GetListedCompanyByCriteria?keyword=&page=1&size=2000',
            'https://www.idx.co.id/umbraco/Api/Company/GetListedCompanies?keyword=&page=1&size=2000',
            'https://www.idx.co.id/umbraco/Surface/ListedCompany/GetListedCompany?page=1&size=2000',
        ]
        for url in idx_urls:
            try:
                import urllib.request
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    text = resp.read().decode('utf-8', errors='ignore')
                try:
                    data = json.loads(text)
                except Exception:
                    data = None

                items = None
                if isinstance(data, dict):
                    for k in ('data', 'rows', 'result', 'results', 'items', 'companies'):
                        if k in data and isinstance(data[k], list):
                            items = data[k]
                            break
                elif isinstance(data, list):
                    items = data

                if not items:
                    # try to find a JSON array inside the HTML
                    import re
                    m = re.search(r"\[\{.+\}\]", text, flags=re.S)
                    if m:
                        try:
                            items = json.loads(m.group(0))
                        except Exception:
                            items = None

                if items and isinstance(items, list):
                    for it in items:
                        if not isinstance(it, dict):
                            continue
                        keys = {k.lower(): v for k, v in it.items()}
                        sym = None
                        name = None
                        for k in ('kodeemiten', 'kode', 'symbol', 'code', 'ticker', 'emitencode'):
                            if k in keys and keys[k]:
                                sym = str(keys[k]).strip()
                                break
                        for k in ('namaperusahaan', 'companyname', 'company', 'name', 'longname', 'shortname'):
                            if k in keys and keys[k]:
                                name = str(keys[k]).strip()
                                break
                        if sym:
                            su = sym.upper()
                            if not su.endswith('.JK'):
                                su = su + '.JK'
                            constituents[su] = name or su
                    if constituents:
                        try:
                            with open(cache_file, 'w', encoding='utf-8') as f:
                                json.dump(constituents, f, ensure_ascii=False, indent=2)
                        except Exception:
                            pass
                        return constituents
            except Exception:
                continue

        # Fallback: use Yahoo search to discover JKT symbols (A-Z)
        letters = [chr(i) for i in range(ord('A'), ord('Z') + 1)]
        seen = set()
        for q in letters:
            try:
                res = self.search_tickers(q, count=80)
            except Exception:
                res = []
            for r in res:
                sym = r.get('symbol')
                name = r.get('name')
                exch = (r.get('exchange') or '').lower()
                if not sym:
                    continue
                su = str(sym).upper()
                if not su.endswith('.JK') and ('jkt' in exch or (name and 'tbk' in name.lower())):
                    su = su + '.JK'
                if su.endswith('.JK') or (name and 'tbk' in name.lower()):
                    if su not in seen:
                        constituents[su] = name or su
                        seen.add(su)
            try:
                time.sleep(0.2)
            except Exception:
                pass

        # If still small, try sector/keyword-based queries which often return many TBK/JKT results
        if len(constituents) < 300:
            sector_queries = [
                'tbk', 'pt', 'indonesia', 'jkt', 'bank', 'property', 'energy', 'mining',
                'resources', 'telecom', 'agro', 'food', 'cement', 'coal', 'metal', 'insurance', 'finance'
            ]
            for q in sector_queries:
                try:
                    res = self.search_tickers(q, count=200)
                except Exception:
                    res = []
                for r in res:
                    sym = r.get('symbol')
                    name = r.get('name')
                    exch = (r.get('exchange') or '').lower()
                    if not sym:
                        continue
                    su = str(sym).upper()
                    if not su.endswith('.JK') and ('jkt' in exch or (name and 'tbk' in name.lower())):
                        su = su + '.JK'
                    if su.endswith('.JK') or (name and 'tbk' in name.lower()):
                        if su not in seen:
                            constituents[su] = name or su
                            seen.add(su)
                try:
                    time.sleep(0.2)
                except Exception:
                    pass

        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(constituents, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        # Additional fallback: try Wikipedia category discovery to fill gaps
        try:
            if len(constituents) < 500:
                wiki_found = self._discover_from_wikipedia()
                for s, n in wiki_found.items():
                    if s not in constituents:
                        constituents[s] = n
        except Exception:
            pass

        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(constituents, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        return constituents

    def _discover_from_wikipedia(self) -> Dict[str, str]:
        """Attempt to discover IDX-listed company names via Wikipedia category pages.

        This method scrapes the "Category:Companies listed on the Indonesia Stock Exchange"
        page and uses `search_tickers` to map company page names to .JK tickers where
        possible. This is an additional fallback when IDX API and Yahoo discovery
        return too few results.
        """
        try:
            import urllib.request
            import re
            import time

            url = 'https://en.wikipedia.org/wiki/Category:Companies_listed_on_the_Indonesia_Stock_Exchange'
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                text = resp.read().decode('utf-8', errors='ignore')

            # Extract links from the category listing (anchor href + link text)
            # Narrow to the mw-category block to avoid unrelated navigation links
            cat_idx = text.find('class="mw-category"')
            block = text[cat_idx:cat_idx+20000] if cat_idx != -1 else text
            # match anchors to company pages; exclude links containing ':' (Category:, File:, etc.)
            entries = re.findall(r'<a href="(/wiki/([^"]+))"[^>]*>([^<]+)</a>', block)
            results: Dict[str, str] = {}
            seen = set()

            for full, path, display in entries:
                # skip names that are category/file/portal links
                if ':' in path:
                    continue
                company = display.strip()
                if not company:
                    continue
                # Use Yahoo search to try mapping the company name to a ticker
                try:
                    candidates = self.search_tickers(company, count=10)
                except Exception:
                    candidates = []

                for c in candidates:
                    sym = c.get('symbol')
                    name = c.get('name') or company
                    exch = (c.get('exchange') or '').lower() or ''
                    if not sym:
                        continue
                    su = str(sym).upper()
                    if not su.endswith('.JK') and ('jkt' in exch or 'idx' in exch or (name and 'tbk' in name.lower())):
                        su = su + '.JK'
                    if su.endswith('.JK') or (name and 'tbk' in name.lower()):
                        if su not in seen:
                            results[su] = name or company
                            seen.add(su)

                try:
                    time.sleep(0.08)
                except Exception:
                    pass

            return results
        except Exception:
            return {}

    def _scrape_idx_api(self) -> Dict[str, str]:
        """Try multiple IDX endpoints with varied headers and parse JSON/HTML.

        Returns a mapping symbol->name when successful, or empty dict.
        """
        try:
            import urllib.request
            import json
            import re
            import time

            idx_urls = [
                'https://www.idx.co.id/umbraco/Surface/ListedCompany/GetListedCompanyByCriteria?keyword=&page=1&size=2000',
                'https://www.idx.co.id/umbraco/Api/Company/GetListedCompanies?keyword=&page=1&size=2000',
                'https://www.idx.co.id/umbraco/Surface/ListedCompany/GetListedCompany?page=1&size=2000',
                'https://www.idx.co.id/en-us/listed-companies/',
                'https://www.idx.co.id/id/beranda/perusahaan-tercatat',
            ]

            header_variants = [
                {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "application/json, text/javascript, */*; q=0.01", "X-Requested-With": "XMLHttpRequest", "Referer": "https://www.idx.co.id/"},
                {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "application/json"},
                {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "text/html"},
            ]

            for url in idx_urls:
                for headers in header_variants:
                    try:
                        req = urllib.request.Request(url, headers=headers)
                        with urllib.request.urlopen(req, timeout=10) as resp:
                            text = resp.read().decode('utf-8', errors='ignore')

                        # Try parse JSON directly
                        try:
                            data = json.loads(text)
                        except Exception:
                            data = None

                        items = None
                        if isinstance(data, dict):
                            for k in ('data', 'rows', 'result', 'results', 'items', 'companies'):
                                if k in data and isinstance(data[k], list):
                                    items = data[k]
                                    break
                        elif isinstance(data, list):
                            items = data

                        constituents = {}
                        if items and isinstance(items, list):
                            for it in items:
                                if not isinstance(it, dict):
                                    continue
                                keys = {k.lower(): v for k, v in it.items()}
                                sym = None
                                name = None
                                for k2 in ('kodeemiten', 'kode', 'symbol', 'code', 'ticker', 'emitencode'):
                                    if k2 in keys and keys[k2]:
                                        sym = str(keys[k2]).strip()
                                        break
                                for k2 in ('namaperusahaan', 'companyname', 'company', 'name', 'longname', 'shortname'):
                                    if k2 in keys and keys[k2]:
                                        name = str(keys[k2]).strip()
                                        break
                                if sym:
                                    su = sym.upper()
                                    if not su.endswith('.JK'):
                                        su = su + '.JK'
                                    constituents[su] = name or su

                            if constituents:
                                return constituents

                        # Try to find JSON array embedded in HTML
                        m = re.search(r"\[\s*\{.+?\}\s*\]", text, flags=re.S)
                        if m:
                            try:
                                items = json.loads(m.group(0))
                                for it in items:
                                    if not isinstance(it, dict):
                                        continue
                                    keys = {k.lower(): v for k, v in it.items()}
                                    sym = None
                                    name = None
                                    for k2 in ('kodeemiten', 'kode', 'symbol', 'code', 'ticker', 'emitencode'):
                                        if k2 in keys and keys[k2]:
                                            sym = str(keys[k2]).strip()
                                            break
                                    for k2 in ('namaperusahaan', 'companyname', 'company', 'name', 'longname', 'shortname'):
                                        if k2 in keys and keys[k2]:
                                            name = str(keys[k2]).strip()
                                            break
                                    if sym:
                                        su = sym.upper()
                                        if not su.endswith('.JK'):
                                            su = su + '.JK'
                                        constituents[su] = name or su
                                if constituents:
                                    return constituents
                            except Exception:
                                pass

                        # Fallback: try parse HTML tables containing code->name pairs
                        rows = re.findall(r'<tr[^>]*>.*?<td[^>]*>([A-Z0-9]{1,6})<\/td>.*?<td[^>]*>([^<]{3,200})<\/td>', text, flags=re.I|re.S)
                        if rows:
                            for code, name in rows:
                                su = code.upper()
                                if not su.endswith('.JK'):
                                    su = su + '.JK'
                                constituents[su] = name.strip()
                            if constituents:
                                return constituents

                        # short pause between attempts
                        try:
                            time.sleep(0.1)
                        except Exception:
                            pass
                    except Exception:
                        continue

            return {}
        except Exception:
            return {}

    def get_all_symbols(self) -> Dict[str, str]:
        """Return merged mapping of Indonesian stocks + commodities + indices."""
        try:
            ihsg = self.get_ihsg_constituents()
        except Exception:
            ihsg = {**INDONESIAN_STOCKS}

        merged = {**ihsg, **COMMODITIES, **INDICES}
        return merged
        
    def search_tickers(self, query: str, count: int = 20) -> List[Dict[str, Any]]:
        """Search ticker candidates using Yahoo Finance search API.

        Returns a list of dicts with keys: `symbol`, `name`, `exchange`.
        This is used as a fallback when the static `ALL_SYMBOLS` mapping
        does not contain a given query/ticker.
        """
        try:
            import urllib.request
            import urllib.parse
            import json

            q = urllib.parse.quote_plus(query)
            url = f"https://query2.finance.yahoo.com/v1/finance/search?q={q}&quotesCount={count}&newsCount=0"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.load(resp)

            quotes = data.get("quotes", []) or []
            results: List[Dict[str, Any]] = []
            for item in quotes:
                sym = item.get("symbol")
                name = item.get("shortname") or item.get("longname") or item.get("name")
                exch = item.get("exchange") or item.get("exchDisp") or item.get("exchangeTimezoneName")
                if sym:
                    results.append({"symbol": sym, "name": name, "exchange": exch})

            return results
        except Exception as e:
            logger.debug(f"search_tickers failed for {query}: {e}")
            return []

    def get_news_for_symbol(self, symbol: str, count: int = 10) -> List[Any]:
        """Fetch recent news items for a specific ticker using yfinance's ticker.news.

        Returns a list of NewsArticle models when possible; otherwise an empty list.
        """
        try:
            import hashlib
            from datetime import datetime as _dt
            from ..models.schemas import NewsArticle

            ticker = yf.Ticker(symbol)
            news = getattr(ticker, 'news', None) or []
            results = []
            for item in news[:count]:
                try:
                    title = item.get('title') or item.get('headline') or ''
                    link = item.get('link') or item.get('url') or ''
                    pub = item.get('providerPublishTime') or item.get('published')
                    if isinstance(pub, (int, float)):
                        published_at = _dt.fromtimestamp(int(pub))
                    else:
                        published_at = _dt.now()
                    summary = item.get('summary') or item.get('content') or ''
                    source = item.get('publisher') or item.get('providerName') or 'Yahoo'
                    aid = hashlib.md5(f"{symbol}_{link}".encode()).hexdigest()[:16]
                    na = NewsArticle(
                        id=aid,
                        title=title,
                        summary=summary[:500],
                        source=source,
                        url=link,
                        published_at=published_at,
                        symbols=[symbol],
                        sentiment_score=0.0,
                    )
                    results.append(na)
                except Exception:
                    continue
            return results
        except Exception as e:
            logger.debug(f"get_news_for_symbol({symbol}) failed: {e}")
            return []
