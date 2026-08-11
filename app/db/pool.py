"""Pooled Postgres connector for NL2SQL Viz.

Wraps asyncpg.create_pool() for connection reuse and concurrent queries.
Provides streaming via server-side cursors for large result sets.
"""

from __future__ import annotations

import datetime
import decimal
import logging
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

import asyncpg

from app.db.guard import validate_read_only
from app.models import ColumnInfo, QueryResult, SchemaMap

logger = logging.getLogger(__name__)

# Types that need coercion for JSON serialization
_COERCE: dict[type, Any] = {
    decimal.Decimal: float,
    datetime.datetime: str,
    datetime.date: str,
    uuid.UUID: str,
    bytes: lambda v: v.hex(),
}


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {k: _COERCE.get(type(v), lambda x: x)(v) for k, v in row.items()}


class PostgresPool:
    """Async connection pool for Postgres with query execution and schema introspection."""

    def __init__(self, dsn: str, min_size: int = 2, max_size: int = 5) -> None:
        self._dsn = dsn
        self._min_size = min_size
        self._max_size = max_size
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(
            self._dsn, min_size=self._min_size, max_size=self._max_size,
        )

    async def disconnect(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    @property
    def is_connected(self) -> bool:
        return self._pool is not None

    # ------------------------------------------------------------------
    # Query execution
    # ------------------------------------------------------------------

    async def execute(self, sql: str, timeout: float = 120.0) -> QueryResult:
        """Execute a read-only SQL query and return typed results."""
        if not self._pool:
            raise RuntimeError("Not connected — call connect() first")
        validate_read_only(sql)

        start = time.monotonic()
        async with self._pool.acquire() as conn:
            async with conn.transaction(readonly=True):
                rows = await conn.fetch(sql, timeout=timeout)

        elapsed_ms = (time.monotonic() - start) * 1000
        normalized = [_normalize_row(dict(r)) for r in rows]
        columns = list(normalized[0].keys()) if normalized else []

        return QueryResult(
            columns=columns,
            rows=normalized,
            row_count=len(normalized),
            execution_time_ms=round(elapsed_ms, 2),
            sql=sql,
        )

    async def execute_raw(self, sql: str, *args: Any) -> None:
        """Execute arbitrary SQL (DDL/inserts) bypassing the read-only guard.

        Internal use only — CSV ingestion and test seeding. Never call this
        with user-supplied SQL.
        """
        if not self._pool:
            raise RuntimeError("Not connected — call connect() first")
        async with self._pool.acquire() as conn:
            await conn.execute(sql, *args)

    async def copy_records(
        self,
        table_name: str,
        columns: list[str],
        records: Any,
    ) -> int:
        """Bulk-load rows via Postgres COPY. Returns the number of rows copied.

        Internal use only — CSV ingestion. ``records`` is an iterable of
        row tuples matching ``columns``.
        """
        if not self._pool:
            raise RuntimeError("Not connected — call connect() first")
        async with self._pool.acquire() as conn:
            await conn.copy_records_to_table(
                table_name, records=records, columns=columns
            )
        return len(records) if hasattr(records, "__len__") else 0

    async def stream(self, sql: str, batch_size: int = 1000) -> AsyncIterator[list[dict[str, Any]]]:
        """Stream results via server-side cursor for large result sets."""
        if not self._pool:
            raise RuntimeError("Not connected — call connect() first")

        async with self._pool.acquire() as conn:
            async with conn.transaction(readonly=True):
                stmt = await conn.prepare(sql)
                batch: list[dict[str, Any]] = []
                async for record in stmt.cursor():
                    batch.append(_normalize_row(dict(record)))
                    if len(batch) >= batch_size:
                        yield batch
                        batch = []
                if batch:
                    yield batch

    # ------------------------------------------------------------------
    # Schema introspection
    # ------------------------------------------------------------------

    async def explain(self, sql: str) -> dict[str, Any]:
        """Run EXPLAIN (FORMAT JSON) and return the plan."""
        if not self._pool:
            raise RuntimeError("Not connected — call connect() first")

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(f"EXPLAIN (FORMAT JSON) {sql}")
        return rows[0]["QUERY PLAN"][0]

    async def get_sample(self, table_name: str, n: int = 5) -> list[dict[str, Any]]:
        """Return up to ``n`` sample rows from a table — bounded, for LLM context.

        Lets the planner/agent see real data values (grain, ranges, formats)
        without loading the whole table. Memory-safe for huge tables.
        """
        if not self._pool:
            raise RuntimeError("Not connected — call connect() first")
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(f'SELECT * FROM "{table_name}" LIMIT {n}')
        return [_normalize_row(dict(r)) for r in rows]

    async def get_schema(self) -> SchemaMap:
        """Introspect the database schema and return a typed SchemaMap."""
        if not self._pool:
            raise RuntimeError("Not connected — call connect() first")

        async with self._pool.acquire() as conn:
            # Fetch columns, constraints, and foreign keys
            raw_cols = await conn.fetch("""
                SELECT
                    t.table_name,
                    c.column_name,
                    c.data_type,
                    c.is_nullable,
                    tc.constraint_type,
                    ccu.table_name AS foreign_table,
                    ccu.column_name AS foreign_column
                FROM information_schema.tables t
                JOIN information_schema.columns c
                    ON t.table_name = c.table_name
                    AND t.table_schema = c.table_schema
                LEFT JOIN information_schema.key_column_usage kcu
                    ON c.column_name = kcu.column_name
                    AND c.table_name = kcu.table_name
                    AND c.table_schema = kcu.table_schema
                LEFT JOIN information_schema.table_constraints tc
                    ON kcu.constraint_name = tc.constraint_name
                    AND t.table_schema = tc.table_schema
                LEFT JOIN information_schema.constraint_column_usage ccu
                    ON tc.constraint_name = ccu.constraint_name
                    AND tc.constraint_schema = ccu.constraint_schema
                    AND tc.constraint_type = 'FOREIGN KEY'
                WHERE t.table_schema = 'public'
                ORDER BY t.table_name, c.ordinal_position
            """)

            # Fetch row estimates from pg_stat
            row_est_rows = await conn.fetch("""
                SELECT relname, n_live_tup
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
            """)

            # Fetch index info
            idx_rows = await conn.fetch("""
                SELECT tablename, indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                ORDER BY tablename, indexname
            """)

        # Build SchemaMap
        tables: list[str] = []
        columns: dict[str, list[ColumnInfo]] = {}
        seen_tables: set[str] = set()

        for row in raw_cols:
            tname = row["table_name"]
            if tname not in seen_tables:
                seen_tables.add(tname)
                tables.append(tname)
                columns[tname] = []
            columns[tname].append(ColumnInfo(
                column=row["column_name"],
                type=row["data_type"],
                nullable=row["is_nullable"] == "YES",
                constraint=row["constraint_type"],
                foreign_table=row["foreign_table"],
                foreign_column=row["foreign_column"],
            ))

        row_estimates = {r["relname"]: r["n_live_tup"] for r in row_est_rows}

        indexes: dict[str, list[str]] = {}
        for r in idx_rows:
            indexes.setdefault(r["tablename"], []).append(r["indexname"])

        return SchemaMap(
            tables=tables,
            columns=columns,
            row_estimates=row_estimates,
            indexes=indexes,
        )
