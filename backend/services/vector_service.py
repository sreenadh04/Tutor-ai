"""
MediTutor AI - Vector Store Service with User Isolation
FAISS-backed semantic search using local sentence-transformers embeddings.
"""

import asyncio
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from config import EMBEDDING_MODEL, TOP_K_CHUNKS, VECTOR_DIR
from services.pdf_service import TextChunk

logger = logging.getLogger(__name__)

_SAFE_ID_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_identifier(value: str) -> str:
    return _SAFE_ID_PATTERN.sub("_", value.strip())


class VectorStoreService:
    USE_IVF_THRESHOLD = 10000

    def __init__(self):
        logger.info("Loading embedding model: %s", EMBEDDING_MODEL)
        self.encoder = SentenceTransformer(EMBEDDING_MODEL)
        self._indexes: Dict[str, Dict[str, faiss.Index]] = {}
        self._metadata: Dict[str, Dict[str, List[dict]]] = {}
        self._executor = ThreadPoolExecutor(max_workers=2)
        logger.info("Embedding model ready")

    def _get_user_vector_dir(self, user_id: str) -> Path:
        if not user_id:
            raise ValueError("user_id is required for vector operations")
        user_dir = VECTOR_DIR / _sanitize_identifier(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

    def _get_doc_vector_dir(self, user_id: str, doc_id: str, create: bool = True) -> Path:
        doc_dir = self._get_user_vector_dir(user_id) / _sanitize_identifier(doc_id)
        if create:
            doc_dir.mkdir(parents=True, exist_ok=True)
        return doc_dir

    def _current_paths(self, user_id: str, doc_id: str) -> Tuple[Path, Path]:
        doc_dir = self._get_doc_vector_dir(user_id, doc_id, create=True)
        return doc_dir / "index.faiss", doc_dir / "metadata.json"

    def _legacy_paths(self, user_id: str, doc_id: str) -> Tuple[Path, Path]:
        user_dir = self._get_user_vector_dir(user_id)
        safe_doc = _sanitize_identifier(doc_id)
        return user_dir / f"{safe_doc}.index", user_dir / f"{safe_doc}.meta.json"

    def _read_paths(self, user_id: str, doc_id: str) -> Tuple[Path, Path]:
        current_index, current_meta = self._current_paths(user_id, doc_id)
        if current_index.exists() and current_meta.exists():
            return current_index, current_meta
        return self._legacy_paths(user_id, doc_id)

    def _ensure_cached(self, user_id: str, doc_id: str):
        self._indexes.setdefault(user_id, {})
        self._metadata.setdefault(user_id, {})

    async def embed_texts_async(self, texts: List[str]) -> np.ndarray:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self._embed_texts_sync, texts)

    def _embed_texts_sync(self, texts: List[str]) -> np.ndarray:
        embeddings = self.encoder.encode(
            texts,
            batch_size=32,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return np.asarray(embeddings, dtype="float32")

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        return self._embed_texts_sync(texts)

    def _create_index(self, embeddings: np.ndarray, use_ivf: bool = False) -> faiss.Index:
        dimension = embeddings.shape[1]
        num_vectors = embeddings.shape[0]

        if use_ivf or num_vectors > self.USE_IVF_THRESHOLD:
            nlist = max(1, min(1024, num_vectors // 100))
            quantizer = faiss.IndexFlatIP(dimension)
            index = faiss.IndexIVFFlat(quantizer, dimension, nlist, faiss.METRIC_INNER_PRODUCT)
            index.train(embeddings)
            index.nprobe = min(max(1, nlist // 10), 32)
            logger.info("Using IVF index with nlist=%s for %s vectors", nlist, num_vectors)
            return index

        logger.info("Using FlatIP index for %s vectors", num_vectors)
        return faiss.IndexFlatIP(dimension)

    async def build_index(
        self,
        user_id: str,
        doc_id: str,
        chunks: List[TextChunk],
        use_ivf: bool = False,
    ) -> int:
        if not user_id:
            raise ValueError("user_id is required")
        if not chunks:
            raise ValueError("No chunks to index")

        texts = [chunk.text for chunk in chunks]
        metadata = [chunk.to_dict() for chunk in chunks]
        embeddings = await self.embed_texts_async(texts)
        index = self._create_index(embeddings, use_ivf=use_ivf)
        index.add(embeddings)

        index_path, meta_path = self._current_paths(user_id, doc_id)
        loop = asyncio.get_running_loop()

        def _write():
            faiss.write_index(index, str(index_path))
            with open(meta_path, "w", encoding="utf-8") as handle:
                json.dump(metadata, handle)

        await loop.run_in_executor(self._executor, _write)

        self._ensure_cached(user_id, doc_id)
        self._indexes[user_id][doc_id] = index
        self._metadata[user_id][doc_id] = metadata
        return index.ntotal

    async def load_index(self, user_id: str, doc_id: str) -> bool:
        if not user_id or not doc_id:
            return False

        self._ensure_cached(user_id, doc_id)
        if self._indexes[user_id].get(doc_id) is not None:
            return True

        index_path, meta_path = self._read_paths(user_id, doc_id)
        if not index_path.exists() or not meta_path.exists():
            return False

        loop = asyncio.get_running_loop()

        def _load():
            index = faiss.read_index(str(index_path))
            with open(meta_path, "r", encoding="utf-8") as handle:
                metadata = json.load(handle)
            return index, metadata

        index, metadata = await loop.run_in_executor(self._executor, _load)
        if hasattr(index, "nprobe"):
            index.nprobe = min(max(1, getattr(index, "nlist", 1) // 10), 32)

        self._indexes[user_id][doc_id] = index
        self._metadata[user_id][doc_id] = metadata
        return True

    async def verify_ownership(self, user_id: str, doc_id: str) -> bool:
        return await self.index_exists(user_id, doc_id)

    async def search(
        self,
        user_id: str,
        doc_id: str,
        query: str,
        top_k: int = TOP_K_CHUNKS,
    ) -> List[Dict]:
        if not user_id or not doc_id:
            raise ValueError("user_id and doc_id are required")

        loaded = await self.load_index(user_id, doc_id)
        if not loaded:
            raise ValueError("Document index not found for this user.")

        index = self._indexes[user_id][doc_id]
        metadata = self._metadata[user_id][doc_id]
        if index is None or metadata is None:
            raise ValueError("Document index failed to load.")

        query_embedding = await self.embed_texts_async([query])
        top_k = max(1, min(top_k, index.ntotal))
        scores, indices = index.search(query_embedding, top_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(metadata):
                continue
            chunk = metadata[idx].copy()
            chunk["relevance_score"] = float(score)
            results.append(chunk)
        return results

    async def index_exists(self, user_id: str, doc_id: str) -> bool:
        if not user_id or not doc_id:
            return False
        index_path, meta_path = self._read_paths(user_id, doc_id)
        return index_path.exists() and meta_path.exists()

    async def delete_index(self, user_id: str, doc_id: str) -> bool:
        if not user_id or not doc_id:
            return False

        deleted = False
        for path in [*self._current_paths(user_id, doc_id), *self._legacy_paths(user_id, doc_id)]:
            if path.exists():
                path.unlink()
                deleted = True

        doc_dir = self._get_doc_vector_dir(user_id, doc_id, create=False)
        if doc_dir.exists():
            try:
                doc_dir.rmdir()
            except OSError:
                pass

        self._indexes.get(user_id, {}).pop(doc_id, None)
        self._metadata.get(user_id, {}).pop(doc_id, None)
        return deleted

    async def list_user_indexes(self, user_id: str) -> List[str]:
        if not user_id:
            return []

        user_dir = self._get_user_vector_dir(user_id)
        doc_ids = {
            path.name
            for path in user_dir.iterdir()
            if path.is_dir() and (path / "index.faiss").exists()
        }
        doc_ids.update(path.stem for path in user_dir.glob("*.index"))
        return sorted(doc_ids)

    async def delete_user_data(self, user_id: str) -> int:
        if not user_id:
            return 0

        user_dir = self._get_user_vector_dir(user_id)
        if not user_dir.exists():
            return 0

        deleted = 0
        for path in sorted(user_dir.rglob("*"), reverse=True):
            try:
                if path.is_file():
                    path.unlink()
                    deleted += 1
                elif path.is_dir():
                    path.rmdir()
            except Exception as exc:
                logger.warning("Failed to delete vector path %s: %s", path, exc)

        self._indexes.pop(user_id, None)
        self._metadata.pop(user_id, None)
        return deleted

    async def health_check(self) -> dict:
        VECTOR_DIR.mkdir(parents=True, exist_ok=True)
        return {
            "available": True,
            "base_dir": str(VECTOR_DIR),
            "model": EMBEDDING_MODEL,
        }

    async def get_stats(self, user_id: Optional[str] = None) -> dict:
        if user_id:
            user_dir = self._get_user_vector_dir(user_id)
            indexes = await self.list_user_indexes(user_id)
            return {
                "user_id": user_id[:8] + "...",
                "total_documents": len(indexes),
                "documents": indexes,
                "storage_path": str(user_dir),
            }

        users = []
        for user_dir in VECTOR_DIR.iterdir():
            if user_dir.is_dir() and not user_dir.name.startswith("."):
                users.append(await self.get_stats(user_dir.name))
        return {
            "total_users": len(users),
            "users": users,
            "base_vector_dir": str(VECTOR_DIR),
        }


vector_service = VectorStoreService()
