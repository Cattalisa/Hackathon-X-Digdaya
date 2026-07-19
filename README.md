# NusaTerminal: Quant AI Trading Assistant

NusaTerminal adalah platform asisten perdagangan (*trading assistant*) bertenaga AI yang khusus dirancang untuk pasar modal Indonesia (IHSG). Platform ini menggabungkan analisis kuantitatif (*Quantitative Analysis*) dan pemrosesan bahasa alami (*Natural Language Processing*) untuk membantu investor mengambil keputusan berbasis data yang akurat.

## 🚀 Fitur Utama

- **Real-Time Market Data & Sync**: Menampilkan harga, volume, dan persentase perubahan secara langsung dengan *Global Sync Loading* agar UI tidak berantakan saat data dimuat.
- **Interactive Candlestick Chart**: Grafik interaktif yang sangat mulus (menggunakan ApexCharts dan animasi Framer Motion) untuk memonitor pergerakan harga saham dengan berbagai periode (1D, 1W, 1M).
- **Quant AI Signals**: Mesin *scoring* kuantitatif berbasis Multi-Factor (Teknikal, Momentum, Sentimen, dan Volume) yang menghasilkan sinyal Beli / Tahan / Jual beserta Rekomendasi Target Harga dan Batas Rugi (Stop Loss).
- **Multithreaded News Sentiment**: Penilaian sentimen berita pasar secara otomatis menggunakan model NLP *Machine Learning*. Didukung teknologi *Multithreading* untuk mengunduh berita dari 12+ portal keuangan lokal secara paralel dalam hitungan detik.
- **Nusa AI Agent (Chatbot)**: Asisten cerdas berbasis AI yang bisa menjawab pertanyaan seputar pasar dan investasi secara real-time langsung di terminal.
- **Epic Dark Mode UI**: Antarmuka bergaya terminal *Bloomberg* modern menggunakan palet warna Acid Green, Glassmorphism, dan Micro-animations yang premium.

## 🏗️ Arsitektur Sistem

Proyek ini dibangun menggunakan arsitektur *microservices/hybrid* berkinerja tinggi yang terdiri dari:

1. **Frontend (Vite + React + TypeScript)**: 
   - Direktori: `/frontend-futures`
   - UI yang responsif dan sangat cepat dengan Tailwind CSS dan animasi `framer-motion`.

2. **Backend (Python + FastAPI)**:
   - Direktori: `/backend`
   - Berjalan di `http://localhost:8000`
   - Menyediakan REST API untuk *Quant Engine*, *News Sentiment*, dan *Chatbot*. 
   - Dilengkapi sistem **Circuit Breaker** (Pencegah Hang) dan *Database Fallback* (SQLite) agar aplikasi tetap menyala secepat kilat meskipun API eksternal sedang gangguan.

3. **Data Scraper (Deno + TypeScript)**:
   - Direktori: `/IDX-API`
   - Berperan sebagai sistem penyedia data API (berjalan di *port* 52060) untuk mengekstraksi data langsung dari sumber IDX.

## 🛠️ Prasyarat

Pastikan perangkat Anda sudah terinstal:
- **Node.js** (v18 atau lebih baru)
- **Python** (v3.10 atau lebih baru)
- **Deno** (Untuk *API Data* tambahan)
- **Git**

## 🚦 Cara Menjalankan Aplikasi

Aplikasi ini memiliki beberapa modul yang harus dijalankan. Anda dapat menjalankannya satu per satu melalui terminal.

### 1. Menjalankan Backend (FastAPI Python)
```bash
# Aktifkan virtual environment (jika ada)
# Untuk Windows:
.\venv\Scripts\activate

# Instal dependensi (hanya saat pertama kali)
pip install -r requirements.txt

# Jalankan server
python -m uvicorn backend.main:app --reload
```
*Backend akan berjalan di port 8000.*

### 2. Menjalankan Frontend (React + Vite)
Buka tab terminal baru:
```bash
cd frontend-futures
npm install
npm run dev
```
*Frontend akan terbuka di browser Anda (biasanya `localhost:5173`).*

### 3. Menjalankan Deno Scraper API (Opsional tapi Direkomendasikan)
Buka tab terminal baru:
```bash
cd IDX-API
deno run --allow-net --allow-read --allow-env main.ts
```
*(Catatan: Sesuaikan nama file utama Deno jika berbeda).*

## 📝 Catatan Penting
- *Disclaimer*: Semua sinyal dan analisis AI di platform ini **hanyalah untuk tujuan edukasi** dan simulasi kompetisi (Hackathon). Ini bukan merupakan nasihat investasi resmi (*financial advice*).

---
*Dibuat untuk Hackathon X Digdaya.*
