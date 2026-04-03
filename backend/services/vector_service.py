"""
MediTutor AI - Vector Store Service
FAISS-backed semantic search with local sentence-transformers embeddings.
100% FREE — no API calls needed for embeddings.
"""

import json
import pickle
import logging
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import faiss
from sentence_transformers import SentenceTransformer

from config import VECTOR_DIR, EMBEDDING_MODEL, EMBEDDING_DIM, TOP_K_CHUNKS
from services.pdf_service import TextChunk

logger = logging.getLogger(__name__)


class VectorStoreService:
    """
    Manages FAISS indexes per document.
    Each document gets its own index stored on disk.
    """

    def __init__(self):
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
        self.encoder = SentenceTransformer(EMBEDDING_MODEL)
        self._indexes: Dict[str, faiss.Index] = {}
        self._metadata: Dict[str, List[dict]] = {}
        logger.info("Embedding model ready")

    # ── File paths ────────────────────────────────────────────────────────────
    def _index_path(self, doc_id: str) -> Path:
        return VECTOR_DIR / f"{doc_id}.index"

    def _meta_path(self, doc_id: str) -> Path:
        return VECTOR_DIR / f"{doc_id}.meta.json"

    # ── Embed ─────────────────────────────────────────────────────────────────
    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """Convert list of strings to embedding matrix."""
        embeddings = self.encoder.encode(
            texts,
            batch_size=32,
            show_progress_bar=False,
            normalize_embeddings=True,   # cosine similarity via inner product
        )
        return embeddings.astype("float32")

    # ── Build index ───────────────────────────────────────────────────────────
    def build_index(self, doc_id: str, chunks: List[TextChunk]) -> int:
        """
        Build a FAISS flat index for a document and persist to disk.
        Returns number of vectors indexed.
        """
        if not chunks:
            raise ValueError("No chunks to index")

        texts = [c.text for c in chunks]
        metadata = [c.to_dict() for c in chunks]

        logger.info(f"Embedding {len(texts)} chunks for doc {doc_id}...")
        embeddings = self.embed_texts(texts)

        # Inner product search (works on normalized vectors = cosine similarity)
        index = faiss.IndexFlatIP(EMBEDDING_DIM)
        index.add(embeddings)

        # Persist
        faiss.write_index(index, str(self._index_path(doc_id)))
        with open(self._meta_path(doc_id), "w") as f:
            json.dump(metadata, f)

        # Cache in memory
        self._indexes[doc_id] = index
        self._metadata[doc_id] = metadata

        logger.info(f"Indexed {index.ntotal} vectors for doc {doc_id}")
        return index.ntotal

    # ── Load index ────────────────────────────────────────────────────────────
    def load_index(self, doc_id: str) -> bool:
        """Load index from disk into memory cache. Returns True if found."""
        if doc_id in self._indexes:
            return True

        idx_path = self._index_path(doc_id)
        meta_path = self._meta_path(doc_id)

        if not idx_path.exists() or not meta_path.exists():
            return False

        self._indexes[doc_id] = faiss.read_index(str(idx_path))
        with open(meta_path) as f:
            self._metadata[doc_id] = json.load(f)

        logger.info(f"Loaded index for doc {doc_id}: {self._indexes[doc_id].ntotal} vectors")
        return True

    # ── Search ────────────────────────────────────────────────────────────────
    def search(
        self,
        doc_id: str,
        query: str,
        top_k: int = TOP_K_CHUNKS,
    ) -> List[Dict]:
        """
        Semantic search. Returns list of chunk dicts with relevance score.
        """
        if not self.load_index(doc_id):
            raise ValueError(f"No index found for document {doc_id}. Re-upload the PDF.")

        index = self._indexes[doc_id]
        metadata = self._metadata[doc_id]

        # Embed query
        q_emb = self.embed_texts([query])

        # Search
        k = min(top_k, index.ntotal)
        scores, indices = index.search(q_emb, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            chunk = metadata[idx].copy()
            chunk["relevance_score"] = float(score)
            results.append(chunk)

        return results

    # ── Index exists check ────────────────────────────────────────────────────
    def index_exists(self, doc_id: str) -> bool:
        return self._index_path(doc_id).exists()

    # ── Delete index ──────────────────────────────────────────────────────────
    def delete_index(self, doc_id: str):
        for path in [self._index_path(doc_id), self._meta_path(doc_id)]:
            if path.exists():
                path.unlink()
        self._indexes.pop(doc_id, None)
        self._metadata.pop(doc_id, None)

    def list_indexes(self) -> List[str]:
        return [p.stem for p in VECTOR_DIR.glob("*.index")]


# ─── Singleton ────────────────────────────────────────────────────────────────
vector_service = VectorStoreService()
