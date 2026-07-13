"""
RAG Document Store - NusaTerminal
Mengelola vector database (ChromaDB) untuk menyimpan dan retrieve
berita, data pasar, dan konteks finansial untuk chatbot RAG.
"""

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from datetime import datetime
from typing import List, Dict, Optional, Any
import json
import uuid
import logging

logger = logging.getLogger(__name__)


class RAGDocumentStore:
    """
    Vector store berbasis ChromaDB untuk RAG chatbot.
    Menyimpan berita dan data pasar sebagai dokumen yang bisa di-retrieve
    berdasarkan semantic similarity dengan query user.
    """

    EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    # Model multilingual yang support Bahasa Indonesia

    def __init__(self, persist_dir: str = "./chroma_db"):
        self.persist_dir = persist_dir
        self._init_chromadb()
        self._init_embedding_model()

    def _init_chromadb(self):
        """Inisialisasi ChromaDB client dengan persistent storage."""
        try:
            self.client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=Settings(anonymized_telemetry=False)
            )

            # Collection untuk berita
            self.news_collection = self.client.get_or_create_collection(
                name="news_articles",
                metadata={"hnsw:space": "cosine"}
            )

            # Collection untuk data pasar & ringkasan
            self.market_collection = self.client.get_or_create_collection(
                name="market_data",
                metadata={"hnsw:space": "cosine"}
            )

            logger.info("✅ ChromaDB berhasil diinisialisasi")

        except Exception as e:
            logger.error(f"Error inisialisasi ChromaDB: {e}")
            raise

    def _init_embedding_model(self):
        """Load sentence transformer untuk embed teks ke vektor."""
        try:
            self.embedder = SentenceTransformer(self.EMBEDDING_MODEL)
            logger.info(f"✅ Embedding model dimuat: {self.EMBEDDING_MODEL}")
        except Exception as e:
            logger.error(f"Error load embedding model: {e}")
            raise

    def _embed(self, texts: List[str]) -> List[List[float]]:
        """Convert list teks menjadi list embedding vektor."""
        return self.embedder.encode(texts).tolist()

    # ─── NEWS INGESTION ───────────────────────────────────────────────────────

    def ingest_news(self, articles: List[Dict]) -> int:
        """
        Simpan berita ke vector store.
        
        Args:
            articles: List dict dengan keys: id, title, summary, source, 
                      published_at, symbols, sentiment_score, url
        Returns:
            Jumlah artikel yang berhasil disimpan
        """
        if not articles:
            return 0

        documents = []
        metadatas = []
        ids = []
        embeddings_input = []

        for article in articles:
            # Buat teks dokumen yang kaya konteks untuk embedding
            doc_text = (
                f"Judul: {article.get('title', '')}\n"
                f"Sumber: {article.get('source', '')}\n"
                f"Ringkasan: {article.get('summary', '')}\n"
                f"Saham terkait: {', '.join(article.get('symbols', []))}"
            )

            article_id = str(article.get('id', uuid.uuid4()))

            documents.append(doc_text)
            metadatas.append({
                "title": article.get('title', ''),
                "source": article.get('source', ''),
                "url": article.get('url', ''),
                "published_at": str(article.get('published_at', datetime.now())),
                "symbols": json.dumps(article.get('symbols', [])),
                "sentiment_score": float(article.get('sentiment_score', 0.0)),
                "type": "news"
            })
            ids.append(f"news_{article_id}")
            embeddings_input.append(doc_text)

        try:
            # Batch embed semua dokumen sekaligus (lebih efisien)
            embeddings = self._embed(embeddings_input)

            # Upsert ke ChromaDB (update jika sudah ada)
            self.news_collection.upsert(
                documents=documents,
                metadatas=metadatas,
                ids=ids,
                embeddings=embeddings
            )

            logger.info(f"✅ {len(articles)} berita disimpan ke vector store")
            return len(articles)

        except Exception as e:
            logger.error(f"Error menyimpan berita: {e}")
            return 0

    def ingest_market_summary(self, symbol: str, summary_text: str, metadata: Dict = None):
        """
        Simpan ringkasan data pasar ke vector store.
        Digunakan untuk memberi konteks data harga ke chatbot.
        """
        doc_id = f"market_{symbol}_{datetime.now().strftime('%Y%m%d%H')}"

        meta = {
            "symbol": symbol,
            "type": "market_summary",
            "updated_at": str(datetime.now()),
        }
        if metadata:
            meta.update({k: str(v) for k, v in metadata.items()})

        try:
            embedding = self._embed([summary_text])
            self.market_collection.upsert(
                documents=[summary_text],
                metadatas=[meta],
                ids=[doc_id],
                embeddings=embedding
            )
        except Exception as e:
            logger.error(f"Error menyimpan market summary {symbol}: {e}")

    # ─── RETRIEVAL ────────────────────────────────────────────────────────────

    def retrieve_relevant_news(
        self,
        query: str,
        n_results: int = 5,
        symbol_filter: Optional[str] = None,
        min_date: Optional[str] = None
    ) -> List[Dict]:
        """
        Retrieve berita yang paling relevan dengan query menggunakan semantic search.
        
        Args:
            query: Pertanyaan user
            n_results: Jumlah dokumen yang dikembalikan
            symbol_filter: Filter hanya berita yang menyebut simbol ini
            min_date: Filter berita setelah tanggal ini (format: YYYY-MM-DD)
            
        Returns:
            List dict berisi dokumen + metadata + similarity score
        """
        try:
            query_embedding = self._embed([query])

            # Guard: empty collection would crash ChromaDB
            collection_count = self.news_collection.count()
            if collection_count == 0:
                return []

            # Build where clause untuk filter
            where_clause = {"type": "news"}

            actual_n = max(1, min(n_results, collection_count))
            results = self.news_collection.query(
                query_embeddings=query_embedding,
                n_results=actual_n,
                where=where_clause,
                include=["documents", "metadatas", "distances"]
            )

            retrieved = []
            for i in range(len(results["ids"][0])):
                meta = results["metadatas"][0][i]
                
                # Post-filter: cek symbol jika diminta
                if symbol_filter:
                    symbols_in_doc = json.loads(meta.get("symbols", "[]"))
                    if symbol_filter not in symbols_in_doc:
                        continue

                retrieved.append({
                    "document": results["documents"][0][i],
                    "metadata": meta,
                    "similarity": 1 - results["distances"][0][i],  # cosine similarity
                    "title": meta.get("title", ""),
                    "source": meta.get("source", ""),
                    "url": meta.get("url", ""),
                    "published_at": meta.get("published_at", ""),
                    "symbols": json.loads(meta.get("symbols", "[]")),
                    "sentiment_score": float(meta.get("sentiment_score", 0.0)),
                })

            # Sort by similarity
            retrieved.sort(key=lambda x: x["similarity"], reverse=True)
            return retrieved[:n_results]

        except Exception as e:
            logger.error(f"Error retrieve berita: {e}")
            return []

    def retrieve_market_context(self, query: str, n_results: int = 3) -> List[Dict]:
        """Retrieve konteks data pasar yang relevan dengan query."""
        try:
            if self.market_collection.count() == 0:
                return []

            query_embedding = self._embed([query])
            results = self.market_collection.query(
                query_embeddings=query_embedding,
                n_results=min(n_results, self.market_collection.count()),
                include=["documents", "metadatas", "distances"]
            )

            return [
                {
                    "document": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "similarity": 1 - results["distances"][0][i],
                }
                for i in range(len(results["ids"][0]))
            ]

        except Exception as e:
            logger.error(f"Error retrieve market context: {e}")
            return []

    def get_collection_stats(self) -> Dict:
        """Statistik vector store."""
        return {
            "news_count": self.news_collection.count(),
            "market_count": self.market_collection.count(),
            "embedding_model": self.EMBEDDING_MODEL,
        }
