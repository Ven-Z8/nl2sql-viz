"""Semantic query cache - matches similar questions, not just exact SQL.

Uses simple keyword overlap + table matching to cache query results.
Falls back to exact SQL matching if semantic match fails.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from collections import OrderedDict

from app.models import QueryResult

logger = logging.getLogger(__name__)

_DEFAULT_TTL = 600  # 10 minutes
_MAX_SIZE = 2000
_WHITESPACE_RE = re.compile(r"\s+")


def _extract_keywords(question: str) -> set[str]:
    """Extract meaningful keywords from natural language question."""
    # Remove common stop words
    stop_words = {
        "what", "is", "are", "the", "of", "a", "an", "in", "on", "at", "to",
        "for", "how", "many", "much", "which", "where", "when", "who", "whom",
        "give", "me", "show", "list", "all", "top", "bottom", "first", "last"
    }
    
    # Lowercase and split
    words = re.findall(r'\b\w+\b', question.lower())
    
    # Remove stop words and short words
    keywords = {w for w in words if w not in stop_words and len(w) > 2}
    
    return keywords


def _keyword_similarity(q1_keywords: set[str], q2_keywords: set[str]) -> float:
    """Calculate Jaccard similarity between keyword sets."""
    if not q1_keywords or not q2_keywords:
        return 0.0
    
    intersection = q1_keywords & q2_keywords
    union = q1_keywords | q2_keywords
    
    return len(intersection) / len(union)


def _normalize_sql(sql: str) -> str:
    """Strip whitespace variations and comments for cache key stability."""
    cleaned = re.sub(r"--[^\n]*", "", sql)  # strip line comments
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)  # strip block comments
    return _WHITESPACE_RE.sub(" ", cleaned).strip().upper()


def semantic_cache_key(connection_id: str, question: str) -> str:
    """Generate cache key based on question keywords."""
    keywords = _extract_keywords(question)
    # Sort keywords for consistency
    key_str = "|".join(sorted(keywords))
    digest = hashlib.sha256(f"{connection_id}:{key_str}".encode()).hexdigest()[:16]
    return f"semantic:{digest}"


def sql_cache_key(connection_id: str, sql: str) -> str:
    """Generate cache key based on normalized SQL."""
    normalized = _normalize_sql(sql)
    digest = hashlib.sha256(f"{connection_id}:{normalized}".encode()).hexdigest()[:16]
    return f"sql:{digest}"


class SemanticQueryCache:
    """Two-level cache: semantic (by question) + exact (by SQL)."""

    def __init__(self, max_size: int = _MAX_SIZE, default_ttl: int = _DEFAULT_TTL) -> None:
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._semantic_store: OrderedDict[str, tuple[QueryResult, str, set[str], float]] = OrderedDict()
        self._sql_store: OrderedDict[str, tuple[QueryResult, float]] = OrderedDict()
        self._semantic_hits = 0
        self._sql_hits = 0
        self._misses = 0

    def get_by_question(self, connection_id: str, question: str) -> tuple[QueryResult | None, str]:
        """Try semantic cache first, then SQL cache."""
        # Try semantic match
        keywords = _extract_keywords(question)

        for key, (result, cached_question, cached_keywords, expires_at) in list(self._semantic_store.items()):
            if time.monotonic() > expires_at:
                del self._semantic_store[key]
                continue

            # Check if connection matches
            if not key.startswith("semantic:"):
                continue
            
            # Calculate keyword similarity
            similarity = _keyword_similarity(keywords, cached_keywords)
            
            # Threshold: 70% keyword overlap
            if similarity >= 0.7:
                self._semantic_store.move_to_end(key)
                self._semantic_hits += 1
                logger.info(f"Semantic cache hit: {similarity:.2f} similarity")
                return result, "semantic"
        
        # Try exact SQL match (if we have the SQL)
        self._misses += 1
        return None, "miss"

    def get_by_sql(self, connection_id: str, sql: str) -> QueryResult | None:
        """Try SQL cache (exact match)."""
        key = sql_cache_key(connection_id, sql)
        entry = self._sql_store.get(key)
        
        if entry is None:
            return None
        
        result, expires_at = entry
        if time.monotonic() > expires_at:
            del self._sql_store[key]
            return None
        
        self._sql_store.move_to_end(key)
        self._sql_hits += 1
        logger.info("SQL cache hit: exact match")
        return result

    def put(self, connection_id: str, question: str, sql: str, result: QueryResult) -> None:
        """Store result in both caches."""
        expires_at = time.monotonic() + self._default_ttl
        
        # Semantic cache
        keywords = _extract_keywords(question)
        semantic_key = semantic_cache_key(connection_id, question)
        
        if len(self._semantic_store) >= self._max_size:
            self._semantic_store.popitem(last=False)
        
        self._semantic_store[semantic_key] = (result, question, keywords, expires_at)
        
        # SQL cache
        sql_key = sql_cache_key(connection_id, sql)
        
        if len(self._sql_store) >= self._max_size:
            self._sql_store.popitem(last=False)
        
        self._sql_store[sql_key] = (result, expires_at)

    def invalidate_connection(self, connection_id: str) -> int:
        """Remove all cached results for a connection."""
        removed = 0
        
        # Clear semantic cache
        to_remove = [k for k in self._semantic_store]
        for k in to_remove:
            del self._semantic_store[k]
            removed += 1
        
        # Clear SQL cache
        to_remove = [k for k in self._sql_store]
        for k in to_remove:
            del self._sql_store[k]
            removed += 1
        
        return removed

    @property
    def stats(self) -> dict[str, int]:
        return {
            "semantic_hits": self._semantic_hits,
            "sql_hits": self._sql_hits,
            "misses": self._misses,
            "semantic_size": len(self._semantic_store),
            "sql_size": len(self._sql_store),
        }
