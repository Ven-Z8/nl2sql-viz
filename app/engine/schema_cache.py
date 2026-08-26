"""Process-wide schema introspection cache.

Introspecting a large Postgres schema costs a fixed ~18s per query because a
fresh ``SchemaAgent`` is built for every WebSocket query. This module-level
cache stores the introspected ``SchemaMap`` per ``(connection_id, dsn-hash)``
with a TTL, so repeat queries skip introspection entirely.

Invalidation: dataset-load / sample-load / CSV-upload endpoints call
``invalidate_dsn`` for the affected database so newly loaded tables are
visible on the next query without waiting for the TTL.
"""

from __future__ import annotations

import hashlib
import logging
import time

from app.models import SchemaMap

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 600  # 10 minutes


def dsn_digest(dsn: str) -> str:
    """Stable short digest of a DSN — never leaks credentials into keys/logs."""
    return hashlib.sha256(dsn.encode()).hexdigest()[:16]


def schema_cache_key(connection_id: str, dsn: str) -> tuple[str, str]:
    """Cache key combining the public connection id and the DSN digest."""
    return (connection_id, dsn_digest(dsn))


class SchemaCache:
    """TTL cache of ``SchemaMap`` entries keyed by (connection_id, dsn)."""

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._store: dict[tuple[str, str], tuple[SchemaMap, float]] = {}
        self._hits = 0
        self._misses = 0

    def get(self, connection_id: str, dsn: str) -> SchemaMap | None:
        """Return the cached schema for this connection, or None on miss/expiry."""
        key = schema_cache_key(connection_id, dsn)
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None
        schema, expires_at = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            self._misses += 1
            return None
        self._hits += 1
        return schema

    def has(self, connection_id: str, dsn: str) -> bool:
        """Non-counting peek used to choose the progress message up front."""
        return self.get(connection_id, dsn) is not None

    def put(self, connection_id: str, dsn: str, schema: SchemaMap) -> None:
        """Store an introspected schema with the configured TTL."""
        self._store[schema_cache_key(connection_id, dsn)] = (
            schema,
            time.monotonic() + self._ttl,
        )

    def invalidate_connection(self, connection_id: str) -> int:
        """Drop every cached schema registered under this connection id."""
        to_remove = [k for k in self._store if k[0] == connection_id]
        for k in to_remove:
            del self._store[k]
        if to_remove:
            logger.info("Schema cache: invalidated %d connection entries", len(to_remove))
        return len(to_remove)

    def invalidate_dsn(self, dsn: str) -> int:
        """Drop every cached schema for this DSN (any connection id).

        Dataset/sample/CSV loads write through the upload database URL, whose
        deterministic connection ids all hash from the same DSN — invalidating
        by DSN covers every owner's view of that database at once.
        """
        digest = dsn_digest(dsn)
        to_remove = [k for k in self._store if k[1] == digest]
        for k in to_remove:
            del self._store[k]
        if to_remove:
            logger.info("Schema cache: invalidated %d entries after data load", len(to_remove))
        return len(to_remove)

    @property
    def stats(self) -> dict[str, int]:
        return {"hits": self._hits, "misses": self._misses, "size": len(self._store)}

    def clear(self) -> None:
        """Test helper — drop every entry."""
        self._store.clear()


_schema_cache: SchemaCache | None = None


def get_schema_cache() -> SchemaCache:
    """Singleton cache shared by every per-query CoordinatorAgent."""
    global _schema_cache
    if _schema_cache is None:
        _schema_cache = SchemaCache()
    return _schema_cache
