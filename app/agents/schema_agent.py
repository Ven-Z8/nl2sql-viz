from typing import Optional

from app.connectors.base import BaseConnector
from app.core.session import SessionStore


class SchemaAgent:
    """
    Introspects the DB and returns a compact schema map string
    suitable for inclusion in Claude prompts.
    Caches per session — invalidated by TTL or explicit call.
    """

    def __init__(
        self,
        connector: BaseConnector,
        session_store: Optional[SessionStore] = None,
        session_id: Optional[str] = None,
    ) -> None:
        self._connector = connector
        self._session_store = session_store
        self._session_id = session_id

    async def get_schema_map(self) -> str:
        # Check cache first
        if self._session_store and self._session_id:
            cached = await self._session_store.get_schema_cache(self._session_id)
            if cached is not None:
                return cached

        schema = await self._connector.get_schema()
        compact = self._build_compact_map(schema)

        if self._session_store and self._session_id:
            await self._session_store.set_schema_cache(self._session_id, compact)

        return compact

    def _build_compact_map(self, schema: dict) -> str:
        lines = []
        for table in schema["tables"]:
            cols = schema["columns"].get(table, [])
            col_strs = []
            for col in cols:
                if col.get("foreign_table") and col.get("foreign_column"):
                    constraint = (
                        f" [FK -> {col['foreign_table']}.{col['foreign_column']}]"
                    )
                elif col["constraint"] == "PRIMARY KEY":
                    constraint = " [PK]"
                elif col["constraint"]:
                    constraint = f" [{col['constraint']}]"
                else:
                    constraint = ""
                col_strs.append(f"{col['column']}:{col['type']}{constraint}")
            lines.append(f"{table}({', '.join(col_strs)})")
        return "\n".join(lines)
