"""SchemaAgent — introspects database schemas for NL2SQL context.

NOOA Agent that:
- Fetches schema from Postgres via the pool
- Caches per-session to avoid repeated introspection
- Provides row estimates from pg_stat_user_tables
- Produces compact text representations for LLM context
"""

from __future__ import annotations

from nooa import Agent, strategy
from nooa.strategies import PredictStrategy

from app.db.pool import PostgresPool
from app.llm import HAIKU
from app.models import SchemaMap


class SchemaAgent(Agent, llm=HAIKU):
    """You are a database schema analyst. You introspect Postgres databases
    and produce compact, accurate schema summaries for SQL generation agents.

    You have access to self.pool (a PostgresPool) for querying the database,
    and self._cache for session-level schema caching.
    """

    pool: PostgresPool
    _cache: SchemaMap | None = None

    # ------------------------------------------------------------------
    # Deterministic helpers (real body → normal Python)
    # ------------------------------------------------------------------

    def get_cached(self) -> SchemaMap | None:
        """Return cached schema if available."""
        return self._cache

    def set_cache(self, schema: SchemaMap) -> None:
        """Store schema in session cache."""
        self._cache = schema

    def compact_map(self, schema: SchemaMap) -> str:
        """Produce compact text representation for LLM context."""
        return schema.compact_repr()

    async def fetch_schema(self) -> SchemaMap:
        """Fetch the full schema from the database."""
        cached = self.get_cached()
        if cached is not None:
            return cached
        schema = await self.pool.get_schema()
        self.set_cache(schema)
        return schema

    # ------------------------------------------------------------------
    # Generation methods (ellipsis body → LLM-driven)
    # ------------------------------------------------------------------

    @strategy(PredictStrategy())
    async def summarize(self, schema_text: str) -> str:
        """Summarize this database schema in 2-3 sentences.
        Focus on: what kind of data it contains, key relationships between tables,
        and which tables are largest. Be specific with table names."""
        ...
