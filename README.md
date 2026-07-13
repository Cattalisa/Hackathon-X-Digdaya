# NusaTerminal: Quant AI Trading Assistant

NusaTerminal adalah platform asisten perdagangan (*trading assistant*) bertenaga AI yang khusus dirancang untuk pasar modal Indonesia (IHSG). Platform ini menggabungkan analisis kuantitatif (*Quantitative Analysis*) dan pemrosesan bahasa alami (*Natural Language Processing*) untuk membantu investor mengambil keputusan berbasis data yang akurat.

## 🚀 Fitur Utama

- **Real-Time Market Data**: Menampilkan harga, volume, dan persentase perubahan secara langsung.
- **Interactive Candlestick Chart**: Grafik interaktif untuk memonitor pergerakan harga saham dengan berbagai periode (1D, 1W, 1M).
- **Quant AI Signals**: Mesin *scoring* kuantitatif berbasis Multi-Factor (Teknikal, Momentum, Sentimen, dan Volume) yang menghasilkan sinyal beli/tahan/jual beserta target harganya.
- **News Sentiment Analysis**: Penilaian sentimen berita pasar secara otomatis (Positif/Negatif/Netral) menggunakan AI.
- **Nusa AI Agent (Chatbot)**: Asisten cerdas berbasis *Retrieval-Augmented Generation* (RAG) dengan vector database `ChromaDB` yang bisa menjawab pertanyaan kompleks seputar investasi saham berdasarkan data terkini.
- **Epic Dark Mode UI**: Antarmuka bergaya terminal *Bloomberg* modern menggunakan palet warna Acid Green dan Glassmorphism.

## 🏗️ Arsitektur Sistem

Proyek ini dibangun menggunakan arsitektur *microservices/hybrid* yang terdiri dari:

1. **Frontend (Next.js + Tailwind CSS)**: 
   - Direktori: `/frontend`
   - Berjalan di `http://localhost:3000`
   - Menyajikan UI dinamis dengan React, komponen Shadcn/UI (Opsional), dan ApexCharts.

2. **Backend (Python + FastAPI)**:
   - Direktori: `/backend`
   - Berjalan di `http://localhost:8000`
   - Menyediakan REST API untuk *Quant Engine*, *News Sentiment*, dan *Chatbot*. 
   - Dilengkapi dengan *background scheduler* untuk sinkronisasi data harga dan berita.

3. **Data Scraper (Deno + TypeScript)**:
   - Direktori: `/idx_scraper`
   - Berperan sebagai sistem bantu (*fallback*) untuk mengekstraksi data langsung dari sumber IDX atau penyedia data lain.

## 🛠️ Prasyarat

Pastikan perangkat Anda sudah terinstal:
- **Node.js** (v18 atau lebih baru)
- **Python** (v3.10 atau lebih baru)
- **Deno** (Untuk *scraper* tambahan)
- **Git**

## 🚦 Cara Menjalankan Aplikasi

Aplikasi ini dilengkapi dengan script instalasi otomatis `start.bat` untuk mempermudah eksekusi di Windows.

### Cara Cepat (Satu Klik)
Cukup jalankan file `start.bat` di terminal/Command Prompt Anda:
```cmd
.\start.bat
```
Script ini akan:
1. Membuka server FastAPI di `localhost:8000`.
2. Menjalankan Deno Scraper.
3. Membuka server Next.js di `localhost:3000`.

### Cara Manual

#### 1. Menjalankan Backend (FastAPI)
```bash
# Aktifkan virtual environment (jika ada)
python -m venv venv
.\venv\Scripts\activate

# Instal dependensi
pip install -r requirements.txt

# Jalankan server
python -m uvicorn backend.main:app --reload
```

#### 2. Menjalankan Frontend (Next.js)
Buka tab terminal baru:
```bash
cd frontend
npm install
npm run dev
```

#### 3. Menjalankan Deno Scraper (Opsional)
Buka tab terminal baru:
```bash
cd idx_scraper
deno run --allow-net --allow-read auto_sync.ts
```

## 📝 Catatan Penting
- *Disclaimer*: Semua sinyal dan analisis AI di platform ini **hanyalah untuk tujuan edukasi** dan simulasi kompetisi (Hackathon). Ini bukan merupakan nasihat investasi resmi (*financial advice*).

---
*Dibuat untuk Hackathon X Digdaya.*
