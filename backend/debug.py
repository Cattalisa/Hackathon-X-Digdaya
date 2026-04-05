"""
NusaTerminal - Debug Script
Jalankan dari root folder Hackathon:
    python debug.py

Script ini akan test setiap komponen satu per satu dan
menunjukkan TEPAT di mana masalahnya.
"""

import sys
import os
import time
import traceback

# ─── WARNA OUTPUT ─────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):    print(f"  {GREEN}✅ {msg}{RESET}")
def fail(msg):  print(f"  {RED}❌ {msg}{RESET}")
def warn(msg):  print(f"  {YELLOW}⚠️  {msg}{RESET}")
def info(msg):  print(f"  {BLUE}ℹ️  {msg}{RESET}")
def header(msg):print(f"\n{BOLD}{'='*60}\n  {msg}\n{'='*60}{RESET}")
def sub(msg):   print(f"\n  {BOLD}── {msg}{RESET}")

RESULTS = {}


# ══════════════════════════════════════════════════════════════════════════════
# TEST 1: PYTHON & ENVIRONMENT
# ══════════════════════════════════════════════════════════════════════════════
header("TEST 1: Python & Environment")

info(f"Python: {sys.version}")
info(f"CWD: {os.getcwd()}")

# Cek apakah kita di folder yang benar
if not os.path.exists("backend"):
    fail("Folder 'backend' tidak ditemukan!")
    fail("Jalankan script ini dari root folder (yang berisi folder 'backend')")
    sys.exit(1)
else:
    ok("Folder 'backend' ditemukan")

if sys.version_info < (3, 10):
    fail(f"Python {sys.version_info.major}.{sys.version_info.minor} terlalu lama, minimal 3.10")
else:
    ok(f"Python versi OK: {sys.version_info.major}.{sys.version_info.minor}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 2: IMPORT DEPENDENCIES
# ══════════════════════════════════════════════════════════════════════════════
header("TEST 2: Import Dependencies")

deps = {
    "fastapi":              "FastAPI",
    "uvicorn":              "Uvicorn",
    "pydantic":             "Pydantic",
    "yfinance":             "yFinance",
    "pandas":               "Pandas",
    "numpy":                "NumPy",
    "feedparser":           "Feedparser",
    "aiohttp":              "aiohttp",
    "cachetools":           "cachetools",
    "chromadb":             "ChromaDB",
    "sentence_transformers":"Sentence Transformers",
    "openai":               "OpenAI client",
    "dotenv":               "python-dotenv",
    "schedule":             "schedule",
}

ml_deps = {
    "torch":        "PyTorch",
    "transformers": "Transformers (HuggingFace)",
}

for pkg, name in deps.items():
    try:
        mod = __import__(pkg)
        ver = getattr(mod, "__version__", "?")
        ok(f"{name} v{ver}")
        RESULTS[f"dep_{pkg}"] = True
    except ImportError as e:
        fail(f"{name}: {e}")
        RESULTS[f"dep_{pkg}"] = False

sub("ML Dependencies (opsional tapi penting untuk sentiment)")
for pkg, name in ml_deps.items():
    try:
        mod = __import__(pkg)
        ver = getattr(mod, "__version__", "?")
        ok(f"{name} v{ver}")
        RESULTS[f"dep_{pkg}"] = True
    except ImportError as e:
        fail(f"{name} TIDAK TERINSTALL: {e}")
        warn(f"  → pip install {pkg}")
        RESULTS[f"dep_{pkg}"] = False


# ══════════════════════════════════════════════════════════════════════════════
# TEST 3: IMPORT BACKEND MODULES
# ══════════════════════════════════════════════════════════════════════════════
header("TEST 3: Import Backend Modules")

sys.path.insert(0, os.getcwd())

modules_to_test = [
    ("backend.models.schemas",          "Schemas"),
    ("backend.services.data_service",   "Data Service"),
    ("backend.services.news_service",   "News Service"),
    ("backend.agents.market_agent",     "Market Agent"),
    ("backend.agents.sentiment_agent",  "Sentiment Agent"),
    ("backend.agents.prediction_agent", "Prediction Agent"),
    ("backend.rag.document_store",      "RAG Document Store"),
    ("backend.agents.chatbot",          "RAG Chatbot"),
]

for module_path, name in modules_to_test:
    try:
        mod = __import__(module_path, fromlist=[""])
        ok(f"{name} ({module_path})")
        RESULTS[f"import_{name}"] = True
    except Exception as e:
        fail(f"{name}: {e}")
        info(f"    Traceback: {traceback.format_exc().splitlines()[-2]}")
        RESULTS[f"import_{name}"] = False


# ══════════════════════════════════════════════════════════════════════════════
# TEST 4: DATA SERVICE & YFINANCE
# ══════════════════════════════════════════════════════════════════════════════
header("TEST 4: Data Service (yFinance)")

try:
    from backend.services.data_service import DataService
    ds = DataService()
    ok("DataService instantiated")

    sub("Test fetch BBCA.JK")
    t0 = time.time()
    data = ds.get_market_data(["BBCA.JK"])
    elapsed = time.time() - t0

    if data and data[0].price > 0:
        ok(f"BBCA.JK: Rp {data[0].price:,.0f} ({data[0].change_percent:+.2f}%) — {elapsed:.1f}s")
        RESULTS["data_service"] = True
    else:
        warn(f"BBCA.JK: harga 0 — mungkin market tutup atau network issue ({elapsed:.1f}s)")
        RESULTS["data_service"] = "partial"

    sub("Test fetch historical BBCA.JK (1mo)")
    hist = ds.get_historical_data("BBCA.JK", "1mo")
    if not hist.empty:
        ok(f"Historical data: {len(hist)} baris, kolom: {list(hist.columns)}")
    else:
        fail("Historical data kosong!")

    sub("Test IHSG")
    ihsg = ds.get_market_summary()
    if ihsg.get("price", 0) > 0:
        ok(f"IHSG: {ihsg['price']:,.0f}")
    else:
        warn("IHSG: 0 — market mungkin tutup")

except Exception as e:
    fail(f"DataService error: {e}")
    traceback.print_exc()
    RESULTS["data_service"] = False


# ══════════════════════════════════════════════════════════════════════════════
# TEST 5: NEWS SERVICE
# ══════════════════════════════════════════════════════════════════════════════
header("TEST 5: News Service (RSS Scraping)")

try:
    from backend.services.news_service import NewsService
    ns = NewsService()
    ok("NewsService instantiated")

    sub("Test fetch_news (general)")
    t0 = time.time()
    news = ns.fetch_news(limit=10)
    elapsed = time.time() - t0
    
    if news:
        ok(f"Fetched {len(news)} artikel dalam {elapsed:.1f}s")
        for i, a in enumerate(news[:3]):
            info(f"  [{i+1}] {a.title[:60]}...")
            info(f"       Symbols: {a.symbols} | Sentiment: {a.sentiment_score}")
        RESULTS["news_fetch"] = True
    else:
        fail("Tidak ada berita yang di-fetch! Cek koneksi internet atau RSS feeds")
        RESULTS["news_fetch"] = False

    sub("Test fetch_news_by_symbol('BBCA')")
    t0 = time.time()
    bbca_news = ns.fetch_news_by_symbol("BBCA", limit=5)
    elapsed = time.time() - t0
    
    if bbca_news:
        ok(f"BBCA: {len(bbca_news)} artikel dalam {elapsed:.1f}s")
        for a in bbca_news[:2]:
            info(f"  - {a.title[:60]}...")
            info(f"    Symbols: {a.symbols} | Sentiment: {a.sentiment_score}")
        RESULTS["news_by_symbol_bbca"] = True
    else:
        fail("BBCA: 0 artikel — cek logic _article_matches dan name_tokens")
        RESULTS["news_by_symbol_bbca"] = False

    sub("Test fetch_news_by_symbol('astra')")
    astra_news = ns.fetch_news_by_symbol("astra", limit=5)
    if astra_news:
        ok(f"astra: {len(astra_news)} artikel")
        for a in astra_news[:2]:
            info(f"  - {a.title[:60]}...")
        RESULTS["news_by_symbol_astra"] = True
    else:
        fail("astra: 0 artikel")
        RESULTS["news_by_symbol_astra"] = False

    sub("Test fetch_news_by_symbol('BYAN')")
    byan_news = ns.fetch_news_by_symbol("BYAN", limit=5)
    if byan_news:
        ok(f"BYAN: {len(byan_news)} artikel")
        for a in byan_news[:2]:
            info(f"  - {a.title[:60]}...")
            info(f"    Symbols: {a.symbols}")
        RESULTS["news_by_symbol_byan"] = True
    else:
        warn("BYAN: 0 artikel (wajar jika tidak ada berita terkini)")
        RESULTS["news_by_symbol_byan"] = "empty_ok"

except Exception as e:
    fail(f"NewsService error: {e}")
    traceback.print_exc()
    RESULTS["news_fetch"] = False


# ══════════════════════════════════════════════════════════════════════════════
# TEST 6: SENTIMENT AGENT (INDOBERT)
# ══════════════════════════════════════════════════════════════════════════════
header("TEST 6: Sentiment Agent (IndoBERT)")

if not RESULTS.get("dep_torch") or not RESULTS.get("dep_transformers"):
    warn("torch atau transformers tidak terinstall — skip sentiment test")
    warn("Install: pip install torch --index-url https://download.pytorch.org/whl/cpu")
    warn("         pip install transformers sentencepiece")
    RESULTS["sentiment"] = False
else:
    try:
        from backend.agents.sentiment_agent import SentimentAgent
        
        sub("Get SentimentAgent singleton")
        from backend.agents.sentiment_agent import get_sentiment_agent
        t0 = time.time()
        sa = get_sentiment_agent()
        ok(f"SentimentAgent singleton dapat dalam {time.time()-t0:.2f}s")
        
        sub("Tunggu model load (max 120 detik)...")
        sa.ensure_model_loaded(timeout=120)
        
        if sa.sentiment_pipeline:
            ok(f"Model loaded: {sa.model_name}")
            RESULTS["sentiment_model"] = True
        else:
            fail("Model GAGAL load — sentiment_pipeline = None")
            fail("Ini penyebab sentiment_score selalu 0.5!")
            warn("Cek log di atas untuk error detail dari _load_model()")
            RESULTS["sentiment_model"] = False

        sub("Cek raw label dari model (diagnosa label mapping)")
        if sa.sentiment_pipeline:
            test_sentences = [
                "Saham naik investor optimis bullish",
                "Saham anjlok investor panik bearish rugi",
                "Harga stabil tidak berubah",
            ]
            info(f"Label map aktif: {sa.label_map}")
            for sent in test_sentences:
                try:
                    raw = sa.sentiment_pipeline(sent)[0]
                    normalized, _ = sa._normalize_label(raw["label"], raw["score"])
                    info(f"  raw=[{raw['label']}:{raw['score']:.3f}] → [{normalized}] | {sent[:40]}")
                except Exception as e:
                    fail(f"  EXCEPTION saat pipeline call: {e}")
                    import traceback; traceback.print_exc()
        else:
            fail("sentiment_pipeline = None! Model tidak berhasil load.")
        
        sub("Test analisis teks langsung")
        test_cases = [
            ("Saham BBCA naik signifikan, investor optimis dengan kinerja perbankan", "positive"),
            ("IHSG anjlok 2%, investor panik akibat sentimen global memburuk", "negative"),
            ("Harga emas stabil di kisaran 3.100 USD per troy ounce", "neutral"),
        ]
        
        all_pass = True
        for text, expected in test_cases:
            result = sa._analyze_single_text(text)
            label = result["label"]
            score = result["score"]
            conf  = result.get("confidence", "N/A")
            match = "✅" if label == expected else "⚠️ "
            print(f"    {match} [{label:8s} score={score:.3f} conf={conf:.3f}] expected=[{expected}] | {text[:40]}...")
            if label != expected:
                all_pass = False
                # Cek apakah ini fallback (score persis 0.5)
                if abs(score - 0.5) < 0.001 and conf == 0.5:
                    fail("    ↳ Score 0.5 PERSIS = FALLBACK! Pipeline gagal dijalankan.")
                    fail("    ↳ Cek output [SentimentAgent] ERROR di atas untuk detail.")
        
        if all_pass:
            ok("Semua test case sentiment sesuai ekspektasi")
            RESULTS["sentiment"] = True
        else:
            warn("Beberapa test case tidak sesuai ekspektasi (mungkin normal)")
            RESULTS["sentiment"] = "partial"

        sub("Test sentiment pada artikel nyata (via singleton)")
        sa.ensure_model_loaded()
        from backend.services.news_service import NewsService
        ns2 = NewsService()
        articles = ns2.fetch_news(limit=5)
        if articles:
            ok(f"Testing {len(articles)} artikel...")
            any_non_default = False
            for a in articles:
                result = sa._aggregate_article_sentiment(a)
                score = result["score"]
                label = result["label"]
                conf  = result.get("confidence", 0.0)
                is_fallback = abs(score - 0.5) < 0.001 and abs(conf - 0.5) < 0.001
                if not is_fallback:
                    any_non_default = True
                flag = f"{RED}← FALLBACK! Cek [SentimentAgent] ERROR di stderr{RESET}" if is_fallback else f"{GREEN}← OK{RESET}"
                print(f"    [{label:8s} score={score:.3f} conf={conf:.3f}] {a.title[:42]}... {flag}")
            if any_non_default:
                ok("Setidaknya satu artikel menghasilkan skor non-fallback ✅")
            else:
                fail("SEMUA artikel masih fallback 0.5 — cek output [SentimentAgent] ERROR di atas")
                info("Kemungkinan penyebab:")
                info("  1. Label map salah (mdhugol: LABEL_0=positive, LABEL_2=negative)")
                info("  2. Exception silent di pipeline (cek stderr)")
        else:
            warn("Tidak ada artikel untuk test")

    except Exception as e:
        fail(f"SentimentAgent error: {e}")
        traceback.print_exc()
        RESULTS["sentiment"] = False


# ══════════════════════════════════════════════════════════════════════════════
# TEST 7: RAG DOCUMENT STORE (CHROMADB)
# ══════════════════════════════════════════════════════════════════════════════
header("TEST 7: RAG Document Store (ChromaDB)")

try:
    from backend.rag.document_store import RAGDocumentStore
    
    sub("Instantiate RAGDocumentStore")
    t0 = time.time()
    store = RAGDocumentStore()
    ok(f"RAGDocumentStore instantiated dalam {time.time()-t0:.2f}s")
    
    stats = store.get_collection_stats()
    info(f"News collection: {stats['news_count']} dokumen")
    info(f"Market collection: {stats['market_count']} dokumen")
    info(f"Embedding model: {stats['embedding_model']}")

    sub("Test embed teks")
    t0 = time.time()
    vec = store._embed(["Test embedding untuk pasar saham Indonesia"])
    elapsed = time.time() - t0
    
    if vec and len(vec[0]) > 0:
        ok(f"Embedding OK: dimensi {len(vec[0])}, dalam {elapsed:.2f}s")
        RESULTS["rag_embed"] = True
    else:
        fail("Embedding gagal menghasilkan vektor!")
        RESULTS["rag_embed"] = False

    sub("Test ingest & retrieve berita")
    test_article = [{
        "id": "debug_test_001",
        "title": "Saham BBCA naik 3% didorong kinerja keuangan positif",
        "summary": "Bank Central Asia mencatat laba bersih meningkat 15%",
        "source": "Debug Test",
        "url": "http://test.com/bbca",
        "published_at": "2026-04-05T10:00:00",
        "symbols": ["BBCA.JK"],
        "sentiment_score": 0.8,
    }]
    
    count = store.ingest_news(test_article)
    if count > 0:
        ok(f"Ingest {count} artikel berhasil")
        
        results = store.retrieve_relevant_news("BBCA saham naik", n_results=1)
        if results:
            ok(f"Retrieve berhasil: '{results[0]['title'][:50]}...' (similarity: {results[0]['similarity']:.3f})")
            RESULTS["rag_store"] = True
        else:
            fail("Retrieve gagal — tidak ada hasil")
            RESULTS["rag_store"] = False
    else:
        fail("Ingest gagal!")
        RESULTS["rag_store"] = False

except Exception as e:
    fail(f"RAGDocumentStore error: {e}")
    traceback.print_exc()
    RESULTS["rag_store"] = False


# ══════════════════════════════════════════════════════════════════════════════
# TEST 8: .ENV FILE & API KEYS
# ══════════════════════════════════════════════════════════════════════════════
header("TEST 8: Environment Variables & API Keys")

env_file = "backend/.env"
if os.path.exists(env_file):
    ok(f".env file ditemukan di {env_file}")
    
    from dotenv import load_dotenv
    load_dotenv(env_file)
    
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
    if deepseek_key and deepseek_key != "your_deepseek_api_key_here":
        ok(f"DEEPSEEK_API_KEY: {'*' * 8}{deepseek_key[-4:]}")
        RESULTS["deepseek_key"] = True
    else:
        fail("DEEPSEEK_API_KEY tidak di-set atau masih placeholder!")
        warn("Edit backend/.env dan isi DEEPSEEK_API_KEY")
        RESULTS["deepseek_key"] = False
else:
    fail(f".env file tidak ditemukan di {env_file}")
    warn("Buat dari template: cp backend/.env.example backend/.env")
    RESULTS["deepseek_key"] = False

sub("Test DeepSeek API connection")
if RESULTS.get("deepseek_key"):
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com/v1"
        )
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": "Jawab singkat: apa itu IHSG?"}],
            max_tokens=50,
        )
        answer = resp.choices[0].message.content
        ok(f"DeepSeek API OK: '{answer[:60]}...'")
        RESULTS["deepseek_api"] = True
    except Exception as e:
        fail(f"DeepSeek API error: {e}")
        RESULTS["deepseek_api"] = False
else:
    warn("Skip DeepSeek API test — API key tidak tersedia")
    RESULTS["deepseek_api"] = False


# ══════════════════════════════════════════════════════════════════════════════
# TEST 9: QUANT PREDICTION AGENT
# ══════════════════════════════════════════════════════════════════════════════
header("TEST 9: Quant Prediction Agent")

try:
    from backend.agents.prediction_agent import QuantPredictionAgent
    from backend.services.data_service import DataService
    
    pa = QuantPredictionAgent()
    ok("QuantPredictionAgent instantiated")
    
    sub("Test analyze_symbol BBCA.JK")
    ds2 = DataService()
    market_data = ds2.get_market_data(["BBCA.JK"])
    
    if market_data and market_data[0].price > 0:
        t0 = time.time()
        signal = pa.analyze_symbol(market_data[0], sentiment=None)
        elapsed = time.time() - t0
        
        if signal:
            import math
            has_nan = any(
                math.isnan(v) or math.isinf(v)
                for v in [signal.composite_score, signal.target_price,
                          signal.stop_loss, signal.atr, signal.confidence]
            )
            
            if has_nan:
                fail(f"NaN/Inf ditemukan di output signal! Ini penyebab /api/signals/dashboard error")
                info(f"  composite_score: {signal.composite_score}")
                info(f"  target_price: {signal.target_price}")
                info(f"  stop_loss: {signal.stop_loss}")
                info(f"  atr: {signal.atr}")
                RESULTS["quant"] = False
            else:
                ok(f"Signal BBCA: {signal.signal.value} (score: {signal.composite_score:+.3f}) dalam {elapsed:.1f}s")
                ok(f"  Target: Rp {signal.target_price:,.0f} | Stop: Rp {signal.stop_loss:,.0f}")
                ok(f"  RSI: {signal.technical.rsi:.1f} | MACD: {signal.technical.macd_crossover}")
                RESULTS["quant"] = True
        else:
            warn("Signal None — data historis mungkin kurang (market tutup?)")
            RESULTS["quant"] = "partial"
    else:
        warn("Market data BBCA = 0, skip quant test")
        RESULTS["quant"] = "partial"

    sub("Test JSON serialization (cek NaN/Inf)")
    try:
        import json, math
        from backend.main import SafeJSONEncoder
        
        test_data = {"score": float("nan"), "price": float("inf"), "normal": 1.5}
        clean = json.loads(json.dumps(test_data, cls=SafeJSONEncoder))
        assert clean["score"] is None
        assert clean["price"] is None
        assert clean["normal"] == 1.5
        ok("SafeJSONEncoder berfungsi: NaN→null, Inf→null")
        RESULTS["json_safe"] = True
    except ImportError:
        warn("SafeJSONEncoder tidak ditemukan di main.py!")
        warn("Ini menyebabkan /api/signals/dashboard error 500")
        RESULTS["json_safe"] = False
    except Exception as e:
        fail(f"SafeJSONEncoder error: {e}")
        RESULTS["json_safe"] = False

except Exception as e:
    fail(f"QuantPredictionAgent error: {e}")
    traceback.print_exc()
    RESULTS["quant"] = False


# ══════════════════════════════════════════════════════════════════════════════
# RINGKASAN AKHIR
# ══════════════════════════════════════════════════════════════════════════════
header("RINGKASAN DEBUG")

print(f"\n{'─'*60}")

critical_issues = []
warnings = []

checks = [
    ("dep_torch",           "PyTorch terinstall",           "pip install torch --index-url https://download.pytorch.org/whl/cpu"),
    ("dep_transformers",    "Transformers terinstall",       "pip install transformers sentencepiece"),
    ("dep_chromadb",        "ChromaDB terinstall",           "pip install chromadb"),
    ("dep_sentence_transformers", "Sentence Transformers",   "pip install sentence-transformers"),
    ("import_News Service", "News Service dapat di-import",  "Cek news_service.py untuk syntax error"),
    ("import_Sentiment Agent", "Sentiment Agent dapat di-import", "Cek sentiment_agent.py"),
    ("news_fetch",          "RSS feeds bisa di-fetch",       "Cek koneksi internet"),
    ("news_by_symbol_bbca", "Berita per simbol berfungsi",   "Cek _article_matches di news_service.py"),
    ("sentiment_model",     "IndoBERT berhasil load",        "pip install torch transformers sentencepiece"),
    ("rag_embed",           "Embedding ChromaDB berfungsi",  "Cek sentence-transformers versi"),
    ("deepseek_key",        "DeepSeek API key di-set",       "Edit backend/.env dan isi DEEPSEEK_API_KEY"),
    ("json_safe",           "SafeJSONEncoder ada di main.py","Replace main.py dengan versi terbaru"),
]

for key, desc, fix in checks:
    val = RESULTS.get(key)
    if val is True or val == "empty_ok":
        print(f"  {GREEN}✅{RESET} {desc}")
    elif val == "partial":
        warnings.append((desc, fix))
        print(f"  {YELLOW}⚠️ {RESET} {desc} (partial)")
    else:
        critical_issues.append((desc, fix))
        print(f"  {RED}❌{RESET} {desc}")

if critical_issues:
    print(f"\n{RED}{BOLD}MASALAH KRITIS yang perlu difix:{RESET}")
    for i, (desc, fix) in enumerate(critical_issues, 1):
        print(f"  {i}. {RED}{desc}{RESET}")
        print(f"     → {fix}")

if warnings:
    print(f"\n{YELLOW}{BOLD}PERINGATAN (tidak kritis):{RESET}")
    for desc, fix in warnings:
        print(f"  ⚠️  {desc}")
        print(f"     → {fix}")

if not critical_issues:
    print(f"\n{GREEN}{BOLD}Semua komponen kritis berfungsi!{RESET}")
    print("Jika masih ada masalah di API, jalankan:")
    print("  uvicorn backend.main:app --reload --log-level debug")

print(f"\n{'─'*60}")
print("Debug selesai.")
