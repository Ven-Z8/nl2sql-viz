import asyncpg
from typing import Any

from .base import BaseConnector


class PostgresConnector(BaseConnector):
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._conn: asyncpg.Connection | None = None

    async def connect(self) -> None:
        self._conn = await asyncpg.connect(self._dsn)

    async def disconnect(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def execute_read(self, sql: str) -> list[dict[str, Any]]:
        sql_upper = sql.strip().upper()
        if not sql_upper.startswith("SELECT") and not sql_upper.startswith("WITH"):
            raise ValueError("read-only queries only (SELECT or WITH)")
        if self._conn is None:
            raise RuntimeError("Not connected — call connect() first")
        rows = await self._conn.fetch(sql)
        return [dict(row) for row in rows]

    async def get_schema(self) -> dict[str, Any]:
        if self._conn is None:
            raise RuntimeError("Not connected — call connect() first")
        rows = await self._conn.fetch("""
            SELECT
                t.table_name,
                c.column_name,
                c.data_type,
                c.is_nullable,
                tc.constraint_type
            FROM information_schema.tables t
            JOIN information_schema.columns c
                ON t.table_name = c.table_name AND t.table_schema = c.table_schema
            LEFT JOIN information_schema.key_column_usage kcu
                ON c.column_name = kcu.column_name AND c.table_name = kcu.table_name
            LEFT JOIN information_schema.table_constraints tc
                ON kcu.constraint_name = tc.constraint_name
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
            })
        return {"tables": list(tables.keys()), "columns": tables}
