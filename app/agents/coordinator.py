"""CoordinatorAgent — orchestrates the full NL2SQL analytics pipeline.

NOOA Agent using CodeActStrategy to coordinate:
1. Schema introspection (SchemaAgent)
2. SQL generation (SQLAgent)
3. Query execution + cost gating
4. Result size management
5. Visualization (VizAgent)
6. Cache lookup/storage

Streams progress events as an async generator for WebSocket delivery.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from nooa import Agent, strategy
from nooa.config import CodeActConfig
from nooa.strategies import CodeActStrategy

from app.agents.schema_agent import SchemaAgent
from app.agents.sql_agent import SQLAgent
from app.agents.viz_agent import VizAgent
from app.db.guard import validate_read_only
from app.engine.cache import QueryCache, cache_key
from app.llm import SONNET


class CoordinatorAgent(Agent, llm=SONNET):
    """You are the analytics coordinator for NL2SQL Viz.
    You orchestrate the full pipeline: schema → SQL → execute → visualize.

    You have access to:
    - self.schema_agent: SchemaAgent for database introspection
    - self.sql_agent: SQLAgent for SQL generation
    - self.viz_agent: VizAgent for chart generation
    - self.cache: QueryCache for result caching
    - self.connection_id: unique identifier for this database connection

    Call the sub-agents' methods in your Python code to complete the pipeline.
    """

    schema_agent: SchemaAgent
    sql_agent: SQLAgent
    viz_agent: VizAgent
    cache: QueryCache
    connection_id: str = "default"

    # ------------------------------------------------------------------
    # Deterministic helpers
    # ------------------------------------------------------------------

    async def run(self, nl_query: str) -> AsyncIterator[dict[str, Any]]:
        """Orchestrate the full pipeline, yielding WebSocket-compatible events."""

        # 1. Cache check
        key = cache_key(self.connection_id, nl_query)
        cached = self.cache.get(key)
        if cached is not None:
            yield {"type": "progress", "message": "Cache hit — returning stored result"}
            plan = self.viz_agent.plan_chart(nl_query, cached)
            chart_spec = self.viz_agent.build_vega_lite(plan, cached)
            yield {
                "type": "result",
                "chart_spec": chart_spec.model_dump(),
                "rows": cached.rows[:100],  # preview for table
                "row_count": cached.row_count,
                "sql": cached.sql,
                "execution_time_ms": cached.execution_time_ms,
                "cached": True,
            }
            return

        # 2. Schema introspection
        yield {"type": "progress", "message": "Analyzing database schema..."}
        schema = await self.schema_agent.fetch_schema()

        # 3. SQL generation via SQLAgent
        yield {"type": "progress", "message": "Generating SQL query..."}
        generated = await self.sql_agent.generate(question=nl_query, schema=schema)

        # 4. Validate and execute
        sql = generated.sql
        validate_read_only(sql)
        yield {"type": "sql", "sql": sql}

        yield {"type": "progress", "message": "Executing query..."}
        result = await self.sql_agent.execute_query(sql)

        if result.row_count == 0:
            yield {"type": "error", "message": "Query returned zero rows. Try a broader question."}
            return

        # 5. Visualization
        yield {"type": "progress", "message": "Building visualization..."}
        plan = self.viz_agent.plan_chart(nl_query, result)
        chart_spec = self.viz_agent.build_vega_lite(plan, result)

        # 6. Cache the result
        self.cache.put(key, result)

        yield {
            "type": "result",
            "chart_spec": chart_spec.model_dump(),
            "rows": result.rows[:100],  # preview for table
            "row_count": result.row_count,
            "sql": sql,
            "execution_time_ms": result.execution_time_ms,
            "cached": False,
        }

    # ------------------------------------------------------------------
    # CodeAct method for complex multi-step analytics
    # ------------------------------------------------------------------

    @strategy(CodeActStrategy(config=CodeActConfig(max_iterations=5)))
    async def analyze(self, question: str) -> dict[str, Any]:
        """Answer a complex analytics question that may require multiple SQL queries.

        Use the sub-agents to:
        1. Get schema context: await self.schema_agent.fetch_schema()
        2. Generate and execute SQL: await self.sql_agent.generate(...) then execute
        3. Compare results across queries if needed
        4. Build visualization: self.viz_agent.plan_chart() + build_vega_lite()

        Return a dict with keys: sql, rows, chart_spec, analysis_summary
        """
        ...
