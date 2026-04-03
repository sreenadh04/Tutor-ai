"""
MediTutor AI - Cache Manager with User Isolation
Disk-based JSON cache with TTL and per-user storage.
"""

import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional

from config import CACHE_DIR, CACHE_TTL, MAX_CACHE_SIZE

logger = logging.getLogger(__name__)

_SAFE_ID_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_identifier(value: str) -> str:
    return _SAFE_ID_PATTERN.sub("_", value.strip())


class CacheManager:
    def __init__(self, cache_dir: Path = CACHE_DIR, ttl: int = CACHE_TTL):
        self.base_cache_dir = Path(cache_dir)
        self.base_cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl
        self._indexes: Dict[str, Dict[str, dict]] = {}

    def _get_user_cache_dir(self, user_id: str, create: bool = True) -> Path:
        if not user_id:
            raise ValueError("user_id is required for cache operations")

        user_dir = self.base_cache_dir / _sanitize_identifier(user_id)
        if create:
            user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

    def _get_index_file(self, user_id: str, create: bool = True) -> Path:
        return self._get_user_cache_dir(user_id, create=create) / "_index.json"

    def _load_index(self, user_id: str) -> Dict[str, dict]:
        if user_id in self._indexes:
            return self._indexes[user_id]

        index_file = self._get_index_file(user_id, create=False)
        if not index_file.exists():
            self._indexes[user_id] = {}
            return self._indexes[user_id]

        try:
            with open(index_file, "r", encoding="utf-8") as handle:
                self._indexes[user_id] = json.load(handle)
        except Exception as exc:
            logger.warning("Failed to load cache index for %s: %s", user_id, exc)
            self._indexes[user_id] = {}
        return self._indexes[user_id]

    def _save_index(self, user_id: str):
        index_file = self._get_index_file(user_id, create=True)
        try:
            with open(index_file, "w", encoding="utf-8") as handle:
                json.dump(self._indexes.get(user_id, {}), handle)
        except Exception as exc:
            logger.warning("Failed to save cache index for %s: %s", user_id, exc)

    def _key_to_path(self, user_id: str, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self._get_user_cache_dir(user_id, create=True) / f"{digest}.json"

    def get(self, user_id: str, key: str) -> Optional[Any]:
        if not user_id:
            return None

        index = self._load_index(user_id)
        entry = index.get(key)
        if not entry:
            return None

        if time.time() > entry.get("expires", 0):
            self.delete(user_id, key)
            return None

        cache_file = self._key_to_path(user_id, key)
        if not cache_file.exists():
            self.delete(user_id, key)
            return None

        try:
            with open(cache_file, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            entry["last_access"] = time.time()
            self._save_index(user_id)
            return data.get("value")
        except Exception as exc:
            logger.warning("Cache read error for user %s key %s: %s", user_id, key, exc)
            return None

    def set(self, user_id: str, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        if not user_id:
            return False

        try:
            index = self._load_index(user_id)
            if len(index) >= MAX_CACHE_SIZE:
                self._evict_oldest(user_id)

            cache_file = self._key_to_path(user_id, key)
            with open(cache_file, "w", encoding="utf-8") as handle:
                json.dump({"value": value, "user_id": user_id}, handle)

            index[key] = {
                "expires": time.time() + (ttl or self.ttl),
                "last_access": time.time(),
                "file": str(cache_file),
            }
            self._save_index(user_id)
            return True
        except Exception as exc:
            logger.warning("Cache write error for user %s key %s: %s", user_id, key, exc)
            return False

    def delete(self, user_id: str, key: str):
        if not user_id:
            return

        index = self._load_index(user_id)
        if key not in index:
            return

        cache_file = self._key_to_path(user_id, key)
        if cache_file.exists():
            cache_file.unlink()
        index.pop(key, None)
        self._save_index(user_id)

    def clear_user_cache(self, user_id: str) -> int:
        if not user_id:
            return 0

        user_dir = self._get_user_cache_dir(user_id, create=False)
        if not user_dir.exists():
            self._indexes.pop(user_id, None)
            return 0

        deleted = 0
        for path in user_dir.glob("*.json"):
            try:
                path.unlink()
                deleted += 1
            except Exception as exc:
                logger.warning("Failed to delete cache file %s: %s", path, exc)

        self._indexes.pop(user_id, None)
        return deleted

    def _evict_oldest(self, user_id: str):
        index = self._load_index(user_id)
        if not index:
            return
        oldest_key = min(index, key=lambda cache_key: index[cache_key].get("last_access", 0))
        self.delete(user_id, oldest_key)

    def clear_expired(self, user_id: Optional[str] = None) -> int:
        if user_id:
            return self._clear_expired_for_user(user_id)

        total = 0
        for user_dir in self.base_cache_dir.iterdir():
            if user_dir.is_dir() and not user_dir.name.startswith("."):
                total += self._clear_expired_for_user(user_dir.name)
        return total

    def _clear_expired_for_user(self, user_id: str) -> int:
        index = self._load_index(user_id)
        now = time.time()
        expired_keys = [key for key, entry in index.items() if entry.get("expires", 0) < now]
        for key in expired_keys:
            self.delete(user_id, key)
        return len(expired_keys)

    def stats(self, user_id: Optional[str] = None) -> dict:
        if user_id:
            index = self._load_index(user_id)
            user_dir = self._get_user_cache_dir(user_id, create=False)
            total_files = len(list(user_dir.glob("*.json"))) if user_dir.exists() else 0
            return {
                "user_id": user_id[:8] + "...",
                "total_items": len(index),
                "total_files": total_files,
                "cache_dir": str(user_dir),
                "ttl_seconds": self.ttl,
                "max_size": MAX_CACHE_SIZE,
            }

        users = []
        for user_dir in self.base_cache_dir.iterdir():
            if user_dir.is_dir() and not user_dir.name.startswith("."):
                users.append(self.stats(user_dir.name))

        return {
            "total_users": len(users),
            "users": users,
            "base_cache_dir": str(self.base_cache_dir),
        }

    def user_exists(self, user_id: str) -> bool:
        if not user_id:
            return False
        user_dir = self._get_user_cache_dir(user_id, create=False)
        return user_dir.exists() and any(user_dir.glob("*.json"))


_cache_instance: Optional[CacheManager] = None


def get_cache() -> CacheManager:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = CacheManager()
    return _cache_instance


cache = get_cache()
