"""Query result cache — LRU with TTL-based expiry.

Keys are normalized SQL strings. Schema changes invalidate all cached
results for that connection.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from collections import OrderedDict

from app.models import QueryResult

logger = logging.getLogger(__name__)

_DEFAULT_TTL = 300  # 5 minutes
_PERSISTENT_TTL = 2592000  # 30 days for semantic cache
_MAX_SIZE = 1000
_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_sql(sql: str) -> str:
    """Strip whitespace variations and comments for cache key stability."""
    cleaned = re.sub(r"--[^\n]*", "", sql)  # strip line comments
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)  # strip block comments
    return _WHITESPACE_RE.sub(" ", cleaned).strip().upper()


def cache_key(connection_id: str, sql: str) -> str:
    normalized = _normalize_sql(sql)
    digest = hashlib.sha256(normalized.encode()).hexdigest()[:16]
    return f"q:{connection_id}:{digest}"

def semantic_cache_key(connection_id: str, question: str) -> str:
    """Generate cache key based on normalized question text."""
    # Normalize: lowercase, strip punctuation, remove common words
    normalized = question.lower().strip()
    # Remove common question words
    for word in ["what", "how", "many", "much", "is", "are", "the", "a", "an"]:
        normalized = normalized.replace(f" {word} ", " ").replace(f"{word} ", " ")
    normalized = " ".join(normalized.split())  # collapse whitespace
    # Hash for consistent key length
    digest = hashlib.sha256(f"{connection_id}:{normalized}".encode()).hexdigest()[:16]
    return f"semantic:{digest}"


class QueryCache:
    """In-memory LRU cache with per-entry TTL."""

    def __init__(self, max_size: int = _MAX_SIZE, default_ttl: int = _DEFAULT_TTL) -> None:
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._store: OrderedDict[str, tuple[QueryResult, float]] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> QueryResult | None:
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None
        result, expires_at = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            self._misses += 1
            return None
        self._store.move_to_end(key)  # LRU: most recently used → end
        self._hits += 1
        return result

    def put(self, key: str, result: QueryResult, ttl: int | None = None) -> None:
        if key in self._store:
            del self._store[key]
        elif len(self._store) >= self._max_size:
            self._store.popitem(last=False)  # evict least recently used
        expires_at = time.monotonic() + (ttl or self._default_ttl)
        self._store[key] = (result, expires_at)

    def invalidate_prefix(self, prefix: str) -> int:
        """Remove all entries whose key starts with prefix. Returns count removed."""
        to_remove = [k for k in self._store if k.startswith(prefix)]
        for k in to_remove:
            del self._store[k]
        return len(to_remove)

    @property
    def stats(self) -> dict[str, int]:
        return {"hits": self._hits, "misses": self._misses, "size": len(self._store)}


class SemanticQueryCache:
    """Persistent semantic cache for question-result pairs.
    
    Stores successful query results indexed by normalized question text.
    Uses 30-day TTL. Persists to disk for cross-session reuse.
    """
    
    def __init__(self, cache_dir: str = ".cache/semantic"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self._memory: dict[str, tuple[dict, float]] = {}
        self._hits = 0
        self._misses = 0
        
    def _cache_path(self, key: str) -> str:
        return os.path.join(self.cache_dir, f"{key}.json")
    
    def get(self, key: str) -> dict | None:
        """Retrieve cached result if valid."""
        # Check memory first
        if key in self._memory:
            result, expires_at = self._memory[key]
            if time.monotonic() < expires_at:
                self._hits += 1
                return result
            else:
                del self._memory[key]
        
        # Check disk
        cache_file = self._cache_path(key)
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    expires_at = data.get("expires_at", 0)
                    if time.time() < expires_at:
                        result = data["result"]
                        self._memory[key] = (result, time.monotonic() + (expires_at - time.time()))
                        self._hits += 1
                        return result
                    else:
                        # Expired, delete
                        os.remove(cache_file)
            except Exception:
                pass
        
        self._misses += 1
        return None
    
    def put(self, key: str, result: dict) -> None:
        """Store result with 30-day TTL."""
        expires_at = time.time() + _PERSISTENT_TTL
        # Memory cache
        self._memory[key] = (result, time.monotonic() + _PERSISTENT_TTL)
        # Disk cache
        cache_file = self._cache_path(key)
        try:
            with open(cache_file, 'w') as f:
                json.dump({"result": result, "expires_at": expires_at}, f)
        except Exception:
            pass
    
    @property
    def stats(self) -> dict[str, int]:
        return {"hits": self._hits, "misses": self._misses, "memory_size": len(self._memory)}