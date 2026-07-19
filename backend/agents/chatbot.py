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
        """Inisialisasi semua LLM generator yang tersedia."""
        self.clients = {}
        
        openai_key = os.getenv("OPENAI_API_KEY")
        gemini_key = os.getenv("GEMINI_API_KEY")
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")

        try:
            if openai_key:
                from openai import OpenAI
                client = OpenAI(api_key=openai_key)
                model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
                self.clients["openai"] = {"client": client, "model": model}
                logger.info(f"✅ OpenAI LLM berhasil diinisialisasi (model: {model})")
                
            if gemini_key:
                try:
                    import google.generativeai as genai
                except ImportError:
                    from google import genai
                
                if 'google.generativeai' in sys.modules:
                    genai.configure(api_key=gemini_key)
                    client = genai
                else:
                    client = genai.Client(api_key=gemini_key)
                    
                model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
                self.clients["gemini"] = {"client": client, "model": model}
                logger.info(f"✅ Gemini LLM berhasil diinisialisasi (model: {model})")

            if deepseek_key and "openai" not in self.clients:
                # DeepSeek hanya sebagai fallback jika OpenAI asli tidak ada
                from openai import OpenAI
                client = OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com/v1")
                model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
                self.clients["openai"] = {"client": client, "model": model} # Alias as openai for processing
                logger.info(f"✅ DeepSeek LLM berhasil diinisialisasi (model: {model})")
                
            if not self.clients:
                logger.warning("Tidak ada API Key yang ditemukan. Set OPENAI_API_KEY, GEMINI_API_KEY, atau DEEPSEEK_API_KEY.")
                
        except Exception as e:
            logger.error(f"Error inisialisasi LLM: {e}")

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

    def _retrieve_context(self, query: str, provided_symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Core RAG retrieval: cari dokumen relevan dari vector store.
        
        Returns dict dengan:
        - news_docs: berita relevan
        - market_docs: data pasar relevan
        - detected_symbol: simbol yang terdeteksi dari query atau context
        """
        detected_symbol = self._extract_symbol_from_query(query)
        if not detected_symbol and provided_symbol:
            # Format to XXXX.JK if needed, but it should already be from frontend
            detected_symbol = provided_symbol

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

    def _generate_single_llm(self, provider: str, prompt: str) -> str:
        """Helper function untuk generate respon dari satu LLM secara terpisah."""
        if provider not in self.clients:
            return "Tidak tersedia."
            
        client = self.clients[provider]["client"]
        model = self.clients[provider]["model"]
        
        try:
            if provider == "openai":
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=1024,
                )
                return response.choices[0].message.content
                
            elif provider == "gemini":
                if hasattr(client, 'GenerativeModel'):
                    model_obj = client.GenerativeModel(model)
                    response = model_obj.generate_content(
                        prompt,
                        generation_config={"temperature": 0.3, "max_output_tokens": 1024}
                    )
                    return response.text
                else:
                    response = client.models.generate_content(
                        model=model,
                        contents=prompt,
                    )
                    return response.text
        except Exception as e:
            logger.error(f"Error {provider} generation: {e}")
            return f"Maaf, {provider} mengalami gangguan."

    def _generate_with_llm(self, prompt: str) -> str:
        """Generate respons menggunakan kolaborasi LLM (jika keduanya ada)."""
        if not self.clients:
            return self._fallback_response(prompt)

        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_openai = executor.submit(self._generate_single_llm, "openai", prompt) if "openai" in self.clients else None
            future_gemini = executor.submit(self._generate_single_llm, "gemini", prompt) if "gemini" in self.clients else None
            
            openai_resp = future_openai.result() if future_openai else None
            gemini_resp = future_gemini.result() if future_gemini else None

        # Jika hanya satu yang tersedia, kembalikan langsung
        if openai_resp and not gemini_resp:
            return openai_resp
        if gemini_resp and not openai_resp:
            return gemini_resp
            
        # Jika keduanya ada, buat konsensus menggunakan OpenAI
        consensus_prompt = (
            "Berikut adalah dua pendapat ahli investasi terkait pasar modal berdasarkan konteks berita yang sama:\n\n"
            f"=== OPINI OPENAI ===\n{openai_resp}\n\n"
            f"=== OPINI GEMINI ===\n{gemini_resp}\n\n"
            "Tugasmu: Sebagai Hakim NusaAI, rumuskan satu kesimpulan akhir yang paling masuk akal, objektif, "
            "dan singkat dari kedua pendapat di atas. Jangan memihak, gabungkan insight terbaik dari keduanya."
        )
        
        consensus_resp = self._generate_single_llm("openai", consensus_prompt)

        # Format output kolaborasi
        final_output = (
            "🤖 **Analisis ChatGPT (OpenAI):**\n"
            f"{openai_resp.strip()}\n\n"
            "⚡ **Analisis Gemini:**\n"
            f"{gemini_resp.strip()}\n\n"
            "🤝 **Konsensus NusaAI:**\n"
            f"{consensus_resp.strip()}"
        )
        return final_output

    def _fallback_response(self, prompt: str) -> str:
        """
        Fallback jika LLM tidak tersedia.
        Tetap gunakan konteks yang di-retrieve, tapi format secara manual.
        """
        return (
            "Maaf, layanan AI sedang tidak tersedia. "
            "Namun berdasarkan berita terkini yang tersedia di database, "
            "kamu bisa mengecek langsung di tab Berita atau Dashboard Sentimen. "
            "\n\n⚠️ Pastikan API KEY (OPENAI_API_KEY / GEMINI_API_KEY / DEEPSEEK_API_KEY) sudah dikonfigurasi di environment atau file .env"
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
        provided_symbol = message.context.get("symbol") if message.context else None
        context = self._retrieve_context(user_query, provided_symbol=provided_symbol)
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
            "llm_active": len(self.clients) > 0,
            "llm_models": [info["model"] for info in self.clients.values()],
        }
