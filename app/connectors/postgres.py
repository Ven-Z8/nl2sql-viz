import asyncpg
import datetime
import uuid
from decimal import Decimal
from typing import Any

from app.core.sql_guard import validate_read_only_sql

from .base import BaseConnector

_COERCE: dict[type, Any] = {
    Decimal: float,
    datetime.datetime: str,
    datetime.date: str,
    uuid.UUID: str,
    bytes: lambda v: v.hex(),
}


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    """Convert asyncpg non-JSON-serializable types to their JSON-safe equivalents."""
    return {k: _COERCE.get(type(v), lambda x: x)(v) for k, v in row.items()}


class PostgresConnector(BaseConnector):
    def __init__(self, dsn: str, command_timeout: float = 30.0) -> None:
        self._dsn = dsn
        self._command_timeout = command_timeout
        self._conn: asyncpg.Connection | None = None

    async def connect(self) -> None:
        self._conn = await asyncpg.connect(
            self._dsn,
            command_timeout=self._command_timeout,
        )

    async def disconnect(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def execute_read(self, sql: str) -> list[dict[str, Any]]:
        validate_read_only_sql(sql)
        if self._conn is None:
            raise RuntimeError("Not connected — call connect() first")
        async with self._conn.transaction(readonly=True):
            rows = await self._conn.fetch(sql)
        return [_normalize_row(dict(row)) for row in rows]

    async def get_schema(self) -> dict[str, Any]:
        if self._conn is None:
            raise RuntimeError("Not connected — call connect() first")
        rows = await self._conn.fetch("""
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
                ON t.table_name = c.table_name AND t.table_schema = c.table_schema
            LEFT JOIN information_schema.key_column_usage kcu
                ON c.column_name = kcu.column_name AND c.table_name = kcu.table_name
                AND c.table_schema = kcu.table_schema
            LEFT JOIN information_schema.table_constraints tc
                ON kcu.constraint_name = tc.constraint_name
                AND kcu.table_schema = tc.table_schema
            LEFT JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name = ccu.constraint_name
                AND tc.constraint_schema = ccu.constraint_schema
                AND tc.constraint_type = 'FOREIGN KEY'
            WHERE t.table_schema = 'public'
            ORDER BY t.table_name, c.ordinal_position
        """)
        tables: dict[str, list] = {}
        for row in rows:
            tname = row["table_name"]
            if tname not in tables:
                tables[tname] = []
            tables[tname].append({
                "column": row["column_name"],
                "type": row["data_type"],
                "nullable": row["is_nullable"] == "YES",
                "constraint": row["constraint_type"],
                "foreign_table": row["foreign_table"],
                "foreign_column": row["foreign_column"],
            })
        return {"tables": list(tables.keys()), "columns": tables}
