"""
MediTutor AI - Cache Manager
Disk-based cache with TTL support. Minimises expensive API calls.
"""

import json
import time
import hashlib
import logging
from pathlib import Path
from typing import Any, Optional
from config import CACHE_DIR, CACHE_TTL, MAX_CACHE_SIZE

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Simple JSON-based disk cache with TTL and LRU-like eviction.
    No external dependencies needed.
    """

    def __init__(self, cache_dir: Path = CACHE_DIR, ttl: int = CACHE_TTL):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl
        self._index_file = self.cache_dir / "_index.json"
        self._index = self._load_index()

    def _load_index(self) -> dict:
        if self._index_file.exists():
            try:
                with open(self._index_file) as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_index(self):
        with open(self._index_file, "w") as f:
            json.dump(self._index, f)

    def _key_to_path(self, key: str) -> Path:
        safe = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{safe}.json"

    def get(self, key: str) -> Optional[Any]:
        if key not in self._index:
            return None
        
        entry = self._index[key]
        if time.time() > entry.get("expires", 0):
            self.delete(key)
            return None
        
        cache_file = self._key_to_path(key)
        if not cache_file.exists():
            self.delete(key)
            return None
        
        try:
            with open(cache_file) as f:
                data = json.load(f)
            # Update access time for LRU
            self._index[key]["last_access"] = time.time()
            self._save_index()
            return data.get("value")
        except Exception as e:
            logger.warning(f"Cache read error for {key}: {e}")
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        try:
            # Evict if at capacity
            if len(self._index) >= MAX_CACHE_SIZE:
                self._evict_oldest()

            expire_time = time.time() + (ttl or self.ttl)
            cache_file = self._key_to_path(key)
            
            with open(cache_file, "w") as f:
                json.dump({"value": value, "key": key}, f)
            
            self._index[key] = {
                "expires": expire_time,
                "last_access": time.time(),
                "file": str(cache_file),
            }
            self._save_index()
            return True
        except Exception as e:
            logger.warning(f"Cache write error for {key}: {e}")
            return False

    def delete(self, key: str):
        if key in self._index:
            cache_file = self._key_to_path(key)
            if cache_file.exists():
                cache_file.unlink()
            del self._index[key]
            self._save_index()

    def _evict_oldest(self):
        if not self._index:
            return
        oldest_key = min(
            self._index.keys(),
            key=lambda k: self._index[k].get("last_access", 0)
        )
        self.delete(oldest_key)

    def clear_expired(self):
        now = time.time()
        expired = [k for k, v in self._index.items() if v.get("expires", 0) < now]
        for k in expired:
            self.delete(k)
        return len(expired)

    def stats(self) -> dict:
        return {
            "total_items": len(self._index),
            "cache_dir": str(self.cache_dir),
            "ttl_seconds": self.ttl,
        }
