"""
RAG Chatbot - NusaTerminal
Chatbot berbasis RAG (Retrieval-Augmented Generation) menggunakan:
- ChromaDB sebagai vector store
- Sentence Transformers untuk embedding
- DeepSeek API sebagai LLM generator (OpenAI-compatible)
- LangChain sebagai orchestrator RAG pipeline
"""

import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any

from openai import OpenAI  # DeepSeek pakai OpenAI-compatible client

from ..models.schemas import ChatMessage, ChatResponse
from ..services.data_service import DataService
from ..services.news_service import NewsService
from ..rag.document_store import RAGDocumentStore

logger = logging.getLogger(__name__)


# ─── SYSTEM PROMPT ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Kamu adalah NusaAI, asisten analisis investasi untuk pasar modal Indonesia.
Kamu membantu investor ritel Indonesia memahami pergerakan saham IDX dan komoditas.

PANDUAN:
- Jawab dalam Bahasa Indonesia yang jelas dan mudah dipahami
- Gunakan konteks berita dan data pasar yang diberikan sebagai basis jawaban
- Jika informasi tidak tersedia di konteks, katakan dengan jujur
- JANGAN memberikan rekomendasi beli/jual yang spesifik — hanya berikan analisis
- Selalu sertakan disclaimer bahwa ini bukan nasihat investasi resmi
- Gunakan format yang rapi dengan poin-poin jika jawabannya panjang

DISCLAIMER yang harus selalu ada di akhir jawaban tentang saham:
"⚠️ Informasi ini hanya untuk tujuan edukasi, bukan nasihat investasi. Keputusan investasi sepenuhnya menjadi tanggung jawab Anda."
"""

RAG_PROMPT_TEMPLATE = """
{system_prompt}

═══════════════════════════════════
KONTEKS BERITA TERKINI (diambil dari database):
{news_context}

═══════════════════════════════════
KONTEKS DATA PASAR:
{market_context}

═══════════════════════════════════
PERTANYAAN USER:
{user_question}

═══════════════════════════════════
Berikan jawaban yang informatif berdasarkan konteks di atas:
"""


class RAGChatbot:
    """
    Chatbot RAG untuk analisis pasar modal Indonesia.
    
    Pipeline:
    1. User query masuk
    2. Query di-embed → semantic search di ChromaDB
    3. Dokumen relevan di-retrieve (berita + data pasar)
    4. Dokumen + query digabung jadi prompt
    5. Gemini generate jawaban berdasarkan konteks nyata
    6. Response dikembalikan ke user
    """

    def __init__(self):
        self.data_service = DataService()
        self.news_service = NewsService()
        self.doc_store = RAGDocumentStore()
        self._init_llm()
        self._sync_news_to_vectorstore()

    def _init_llm(self):
        """Inisialisasi DeepSeek API sebagai LLM generator (OpenAI-compatible)."""
        api_key = os.getenv("DEEPSEEK_API_KEY")
        self.llm_model = "none"  # Default; akan di-override jika API key valid
        if not api_key:
            logger.warning(
                "DEEPSEEK_API_KEY tidak ditemukan. "
                "Set environment variable DEEPSEEK_API_KEY untuk mengaktifkan LLM."
            )
            self.client = None
            return

        try:
            # DeepSeek menggunakan OpenAI-compatible API
            self.client = OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com/v1",
            )
            self.llm_model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
            logger.info(f"✅ DeepSeek LLM berhasil diinisialisasi (model: {self.llm_model})")
        except Exception as e:
            logger.error(f"Error inisialisasi DeepSeek: {e}")
            self.client = None

    def _sync_news_to_vectorstore(self):
        """
        Fetch berita terbaru dan simpan ke vector store.
        Dipanggil saat inisialisasi dan bisa dipanggil periodic.
        """
        try:
            articles = self.news_service.fetch_news(limit=50)
            if not articles:
                return

            # Convert NewsArticle objects ke dict
            articles_dicts = [
                {
                    "id": a.id,
                    "title": a.title,
                    "summary": a.summary,
                    "source": a.source,
                    "url": a.url,
                    "published_at": a.published_at,
                    "symbols": a.symbols,
                    "sentiment_score": a.sentiment_score,
                }
                for a in articles
            ]

            count = self.doc_store.ingest_news(articles_dicts)
            logger.info(f"✅ {count} berita disync ke vector store")

            # Sync juga data pasar
            self._sync_market_to_vectorstore()

        except Exception as e:
            logger.error(f"Error sync berita: {e}")

    def _sync_market_to_vectorstore(self):
        """Simpan ringkasan data pasar terbaru ke vector store."""
        try:
            market_data_list = self.data_service.get_market_data()
            for market_data in market_data_list:
                if market_data.price <= 0:
                    continue

                summary = (
                    f"Data pasar {market_data.name} ({market_data.symbol}) "
                    f"pada {market_data.last_update.strftime('%d %B %Y %H:%M')}:\n"
                    f"Harga saat ini: Rp {market_data.price:,.2f}\n"
                    f"Perubahan: {market_data.change_percent:+.2f}% (Rp {market_data.change:+,.2f})\n"
                    f"Volume: {market_data.volume:,} lembar\n"
                    f"Range hari ini: Rp {market_data.low:,.2f} – Rp {market_data.high:,.2f}\n"
                    f"Open: Rp {market_data.open:,.2f}"
                )

                self.doc_store.ingest_market_summary(
                    symbol=market_data.symbol,
                    summary_text=summary,
                    metadata={
                        "price": market_data.price,
                        "change_percent": market_data.change_percent,
                    }
                )

        except Exception as e:
            logger.error(f"Error sync market data: {e}")

    # ─── RETRIEVAL ─────────────────────────────────────────────────────────────

    def _extract_symbol_from_query(self, query: str) -> Optional[str]:
        """Ekstrak simbol saham dari query user."""
        stock_map = {
            "bbca": "BBCA.JK", "bca": "BBCA.JK",
            "bbri": "BBRI.JK", "bri": "BBRI.JK",
            "bmri": "BMRI.JK", "mandiri": "BMRI.JK",
            "bbni": "BBNI.JK", "bni": "BBNI.JK",
            "tlkm": "TLKM.JK", "telkom": "TLKM.JK",
            "asii": "ASII.JK", "astra": "ASII.JK",
            "unvr": "UNVR.JK", "unilever": "UNVR.JK",
            "antm": "ANTM.JK", "antam": "ANTM.JK",
            "indf": "INDF.JK", "indofood": "INDF.JK",
            "ihsg": "^JKSE", "jkse": "^JKSE",
            "emas": "GC=F", "gold": "GC=F",
            "cpo": "FCPO", "sawit": "FCPO",
        }

        query_lower = query.lower()
        for keyword, symbol in stock_map.items():
            if keyword in query_lower:
                return symbol

        # Cek format XXXX.JK langsung
        import re
        match = re.search(r'\b([A-Z]{4})\.JK\b', query.upper())
        if match:
            return match.group(0)

        return None

    def _retrieve_context(self, query: str) -> Dict[str, Any]:
        """
        Core RAG retrieval: cari dokumen relevan dari vector store.
        
        Returns dict dengan:
        - news_docs: berita relevan
        - market_docs: data pasar relevan
        - detected_symbol: simbol yang terdeteksi dari query
        """
        detected_symbol = self._extract_symbol_from_query(query)

        # Retrieve berita relevan
        news_docs = self.doc_store.retrieve_relevant_news(
            query=query,
            n_results=5,
            symbol_filter=detected_symbol
        )

        # Jika filter symbol tidak ada hasil, coba tanpa filter
        if not news_docs and detected_symbol:
            news_docs = self.doc_store.retrieve_relevant_news(
                query=query,
                n_results=5
            )

        # Retrieve data pasar relevan
        market_docs = self.doc_store.retrieve_market_context(
            query=query,
            n_results=3
        )

        return {
            "news_docs": news_docs,
            "market_docs": market_docs,
            "detected_symbol": detected_symbol
        }

    def _format_context(self, news_docs: List[Dict], market_docs: List[Dict]) -> tuple[str, str]:
        """Format dokumen yang di-retrieve menjadi teks konteks untuk prompt."""

        # Format berita
        if news_docs:
            news_parts = []
            for i, doc in enumerate(news_docs, 1):
                sim_pct = f"{doc['similarity']*100:.0f}%"
                news_parts.append(
                    f"[Berita {i}] (Relevansi: {sim_pct})\n"
                    f"Judul: {doc['title']}\n"
                    f"Sumber: {doc['source']} | {doc['published_at'][:16]}\n"
                    f"Isi: {doc['document']}\n"
                )
            news_context = "\n".join(news_parts)
        else:
            news_context = "Tidak ada berita relevan ditemukan di database saat ini."

        # Format data pasar
        if market_docs:
            market_parts = [doc["document"] for doc in market_docs]
            market_context = "\n---\n".join(market_parts)
        else:
            market_context = "Data pasar belum tersedia. Coba refresh atau tunggu sebentar."

        return news_context, market_context

    # ─── GENERATION ────────────────────────────────────────────────────────────

    def _generate_with_llm(self, prompt: str) -> str:
        """Generate respons menggunakan DeepSeek LLM."""
        if not self.client:
            return self._fallback_response(prompt)

        try:
            response = self.client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1024,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error DeepSeek generation: {e}")
            return self._fallback_response(prompt)

    def _fallback_response(self, prompt: str) -> str:
        """
        Fallback jika DeepSeek tidak tersedia.
        Tetap gunakan konteks yang di-retrieve, tapi format secara manual.
        """
        return (
            "Maaf, layanan AI sedang tidak tersedia. "
            "Namun berdasarkan berita terkini yang tersedia di database, "
            "kamu bisa mengecek langsung di tab Berita atau Dashboard Sentimen. "
            "\n\n⚠️ Pastikan DEEPSEEK_API_KEY sudah dikonfigurasi di file .env"
        )

    # ─── MAIN INTERFACE ────────────────────────────────────────────────────────

    async def process_message(self, message: ChatMessage) -> ChatResponse:
        """
        Process pesan user melalui pipeline RAG lengkap.
        
        Flow:
        1. Sync berita terbaru ke vector store (jika diperlukan)
        2. Retrieve dokumen relevan berdasarkan query
        3. Format konteks
        4. Generate jawaban dengan LLM
        5. Return ChatResponse
        """
        user_query = message.message.strip()

        if not user_query:
            return ChatResponse(
                response="Silakan ketik pertanyaanmu tentang pasar saham Indonesia.",
                sources=[],
                timestamp=datetime.now()
            )

        # 1. Retrieve konteks dari vector store
        context = self._retrieve_context(user_query)
        news_docs = context["news_docs"]
        market_docs = context["market_docs"]
        detected_symbol = context["detected_symbol"]

        # 2. Format konteks menjadi teks
        news_context, market_context = self._format_context(news_docs, market_docs)

        # 3. Build RAG prompt
        full_prompt = RAG_PROMPT_TEMPLATE.format(
            system_prompt=SYSTEM_PROMPT,
            news_context=news_context,
            market_context=market_context,
            user_question=user_query
        )

        # 4. Generate jawaban dengan LLM
        response_text = self._generate_with_llm(full_prompt)

        # 5. Kumpulkan sources dari dokumen yang di-retrieve
        sources = []
        for doc in news_docs:
            if doc.get("url"):
                sources.append(doc["url"])
            elif doc.get("source"):
                sources.append(doc["source"])

        return ChatResponse(
            response=response_text,
            sources=sources[:5],  # Max 5 sumber
            timestamp=datetime.now()
        )

    def refresh_knowledge_base(self):
        """
        Manual refresh vector store dengan berita dan data terbaru.
        Bisa dipanggil dari scheduler atau endpoint API.
        """
        logger.info("Refreshing knowledge base...")
        self._sync_news_to_vectorstore()
        logger.info("✅ Knowledge base berhasil diperbarui")

    def get_stats(self) -> Dict:
        """Statistik RAG system."""
        return {
            "vector_store": self.doc_store.get_collection_stats(),
            "llm_active": self.client is not None,
            "llm_model": self.llm_model if hasattr(self, "llm_model") and self.client else "none",
        }
