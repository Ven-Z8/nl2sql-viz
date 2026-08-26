"""Unit tests for the process-wide schema introspection cache (T3).

Repeat queries must skip the ~18s introspection; entries expire after the TTL
and are invalidated per-connection or per-DSN when datasets/samples/uploads
change the database.
"""
import pytest

from app.engine.schema_cache import (
    DEFAULT_TTL_SECONDS,
    SchemaCache,
    get_schema_cache,
    schema_cache_key,
)
from app.models import ColumnInfo, SchemaMap


def _schema(table: str = "orders") -> SchemaMap:
    return SchemaMap(
        tables=[table],
        columns={table: [ColumnInfo(column="id", type="integer")]},
        row_estimates={table: 100},
        indexes={table: []},
    )


@pytest.fixture()
def cache() -> SchemaCache:
    return SchemaCache()


def test_miss_then_hit_within_ttl(cache):
    assert cache.get("conn-1", "postgresql://a") is None
    assert cache.stats["misses"] == 1

    schema = _schema()
    cache.put("conn-1", "postgresql://a", schema)
    assert cache.get("conn-1", "postgresql://a") is schema
    assert cache.stats == {"hits": 1, "misses": 1, "size": 1}


def test_keys_are_isolated_per_connection_and_dsn(cache):
    cache.put("conn-1", "postgresql://a", _schema("a_conn1"))
    # Different connection id → miss
    assert cache.get("conn-2", "postgresql://a") is None
    # Same connection id, different DSN → miss
    assert cache.get("conn-1", "postgresql://b") is None
    # The DSN digest must never appear in any retrievable key material test:
    key = schema_cache_key("conn-1", "secret-password-dsn")
    assert "secret-password-dsn" not in str(key)
    assert key[0] == "conn-1" and len(key[1]) == 16


def test_ttl_expiry_returns_none(cache):
    short = SchemaCache(ttl_seconds=1)
    short.put("conn-1", "postgresql://a", _schema())
    # Simulate expiry without sleeping a full second: rewind the timestamp.
    key = schema_cache_key("conn-1", "postgresql://a")
    schema, expires_at = short._store[key]
    short._store[key] = (schema, expires_at - (DEFAULT_TTL_SECONDS + 2))
    assert short.get("conn-1", "postgresql://a") is None
    assert key not in short._store  # expired entry evicted


def test_invalidate_connection_only_touches_that_connection(cache):
    cache.put("conn-1", "postgresql://a", _schema("s1"))
    cache.put("conn-2", "postgresql://a", _schema("s2"))
    removed = cache.invalidate_connection("conn-1")
    assert removed == 1
    assert cache.get("conn-1", "postgresql://a") is None
    assert cache.get("conn-2", "postgresql://a") is not None


def test_invalidate_dsn_covers_all_connections_of_that_dsn(cache):
    cache.put("conn-1", "postgresql://shared", _schema("s1"))
    cache.put("conn-2", "postgresql://shared", _schema("s2"))
    cache.put("conn-3", "postgresql://other", _schema("s3"))
    removed = cache.invalidate_dsn("postgresql://shared")
    assert removed == 2
    assert cache.get("conn-1", "postgresql://shared") is None
    assert cache.get("conn-2", "postgresql://shared") is None
    assert cache.get("conn-3", "postgresql://other") is not None


def test_singleton_is_stable():
    assert get_schema_cache() is get_schema_cache()
    get_schema_cache().clear()  # don't leak state into other tests
