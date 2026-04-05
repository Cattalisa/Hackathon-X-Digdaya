# NusaTerminal — Bloomberg Terminal untuk Investor Ritel Indonesia

Platform analisis investasi berbasis AI yang mendemokratisasi akses data grade institusi
untuk investor ritel Indonesia.

---

## 🧠 Arsitektur AI

### Sentiment Agent (IndoBERT)
- Model: `mdhugol/indonesia-bert-sentiment-classification` (IndoBERT fine-tuned)
- Fallback: `nlptown/bert-base-multilingual-uncased-sentiment`
- Cara kerja: Setiap berita di-analisis AI (judul + summary) → skor sentimen per saham
- **Bukan keyword matching** — AI memahami konteks kalimat

### RAG Chatbot (ChromaDB + Gemini)
- Vector store: ChromaDB (persistent, lokal)
- Embedding: `paraphrase-multilingual-MiniLM-L12-v2` (support Bahasa Indonesia)
- LLM: Gemini 1.5 Flash (gratis, cepat)
- Cara kerja: Query user → semantic search → retrieve berita relevan → Gemini jawab berdasarkan konteks nyata
- **Bukan if-else** — AI generate jawaban dari konteks berita aktual

---

## 🚀 Setup & Instalasi

### 1. Clone & Setup Environment
```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Konfigurasi API Key
```bash
cp .env.example .env
# Edit .env, isi GEMINI_API_KEY
# Dapatkan gratis di: https://makersuite.google.com/app/apikey
```

### 3. Jalankan Server
```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Akses API
- Swagger UI: http://localhost:8000/docs
- Health check: http://localhost:8000/health

---

## 📁 Struktur Project

```
backend/
├── main.py                    # FastAPI app + endpoints + scheduler
├── requirements.txt
├── .env.example
├── agents/
│   ├── market_agent.py        # Fetch data pasar real-time (yfinance)
│   ├── sentiment_agent.py     # AI sentiment (IndoBERT) ← DIUBAH TOTAL
│   ├── prediction_agent.py    # Sinyal trading (price + sentiment)
│   └── chatbot.py             # RAG chatbot (ChromaDB + Gemini) ← DIUBAH TOTAL
├── services/
│   ├── data_service.py        # yfinance data layer + cache
│   └── news_service.py        # RSS news scraping
├── models/
│   └── schemas.py             # Pydantic data models
└── rag/
    └── document_store.py      # ChromaDB vector store manager ← BARU
```

---

## 🔌 API Endpoints

### Market
| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/api/market` | Data pasar semua saham |
| GET | `/api/market/movers` | Top gainers/losers |
| GET | `/api/market/ihsg` | Data IHSG |
| GET | `/api/market/historical/{symbol}` | Data historis OHLCV |

### Sentiment (AI-Powered)
| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/api/sentiment` | Sentimen semua saham (IndoBERT) |
| GET | `/api/sentiment/dashboard` | Dashboard sentimen |
| GET | `/api/sentiment/{symbol}` | Sentimen satu saham |

### Signals
| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/api/signals` | Sinyal trading semua saham |
| GET | `/api/signals/summary` | Ringkasan sinyal |

### Chatbot (RAG)
| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| POST | `/api/chat` | Chat dengan RAG chatbot |
| POST | `/api/chat/refresh` | Refresh knowledge base |
| GET | `/api/chat/stats` | Statistik vector store |

---

## 💬 Contoh Chat Request

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Kenapa BBCA turun hari ini?", "user_id": "user1"}'
```

Response akan berisi jawaban Gemini yang di-ground pada berita aktual dari ChromaDB.

---

## ⚠️ Disclaimer

Platform ini hanya untuk tujuan edukasi dan analisis.
Bukan merupakan nasihat investasi resmi.
Keputusan investasi sepenuhnya menjadi tanggung jawab pengguna.
