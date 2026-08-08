"""CoordinatorAgent — orchestrates the full NL2SQL analytics pipeline.

NOOA Agent using CodeActStrategy to coordinate:
1. Schema introspection (SchemaAgent)
2. Query planning / decomposition (QueryPlanner)
3. SQL generation (SQLAgent)
4. Query execution + cost gating
5. Grounded answer assembly (deterministic — every number from real data)
6. Visualization (VizAgent)
7. Cache lookup/storage

Streams progress events as an async generator for WebSocket delivery.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from typing import Any

from nooa import Agent, strategy
from nooa.config import CodeActConfig
from nooa.strategies import CodeActStrategy

from app.agents.planner import QueryPlanner
from app.agents.schema_agent import SchemaAgent
from app.agents.sql_agent import SQLAgent
from app.agents.viz_agent import VizAgent
from app.db.guard import validate_read_only
from app.engine.cache import QueryCache, cache_key
from app.llm import SONNET
from app.models import (
    GroundedAnswer,
    Metric,
    QueryResult,
    QueryType,
    SubQuery,
)

_KPI_HINTS = ("how many", "total", "what is", "what's", "count of", "sum of", "average", "avg ")
_TREND_HINTS = ("over time", "trend", "monthly", "weekly", "daily", "quarterly", "by month", "by date", "by year")
_COMPARISON_HINTS = ("vs", "versus", "compare", "compared", "difference between")
_DISTRIBUTION_HINTS = ("distribution", "histogram", "spread of", "range of")


def _fmt(value: float) -> str:
    """Format a number for display: thousands separators, trimmed decimals."""
    if abs(value) >= 1000:
        return f"{value:,.2f}".rstrip("0").rstrip(".")
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _title(label: str) -> str:
    return label.replace("_", " ").title()


def _sample_text(table_name: str, sample: list[dict[str, Any]]) -> str:
    """Render sample rows as a compact table for LLM context."""
    if not sample:
        return ""
    columns = list(sample[0].keys())
    header = " | ".join(columns)
    lines = [f"Sample data from {table_name} (first {len(sample)} rows):", header]
    for row in sample:
        lines.append(" | ".join(str(row.get(c, ""))[:24] for c in columns))
    return "\n".join(lines)


class CoordinatorAgent(Agent, llm=SONNET):
    """You are the analytics coordinator for NL2SQL Viz.
    You orchestrate the full pipeline: schema → plan → SQL → execute → answer → visualize.

    You have access to:
    - self.schema_agent: SchemaAgent for database introspection
    - self.planner: QueryPlanner for decomposing complex questions
    - self.sql_agent: SQLAgent for SQL generation
    - self.viz_agent: VizAgent for chart generation
    - self.cache: QueryCache for result caching
    - self.connection_id: unique identifier for this database connection

    Call the sub-agents' methods in your Python code to complete the pipeline.
    """

    schema_agent: SchemaAgent
    planner: QueryPlanner | None = None
    sql_agent: SQLAgent
    viz_agent: VizAgent
    cache: QueryCache
    connection_id: str = "default"
    focus_table: str | None = None

    # ------------------------------------------------------------------
    # Deterministic helpers
    # ------------------------------------------------------------------

    def infer_query_type(self, question: str, result: QueryResult) -> QueryType:
        """Classify the question deterministically (no LLM) from hints + result shape."""
        q = question.lower()
        if any(h in q for h in _TREND_HINTS):
            return QueryType.TREND
        if any(h in q for h in _COMPARISON_HINTS):
            return QueryType.COMPARISON
        if any(h in q for h in _DISTRIBUTION_HINTS):
            return QueryType.DISTRIBUTION
        # "by <dimension>" with multiple rows → breakdown, even if it says "total"
        if re.search(r"\bby\s+[a-z_]+", q) and result.row_count > 1:
            return QueryType.BREAKDOWN
        if any(h in q for h in _KPI_HINTS) or result.row_count == 1:
            return QueryType.KPI
        return QueryType.BREAKDOWN

    def extract_metrics(self, query_type: QueryType, results: list[QueryResult]) -> list[Metric]:
        """Extract grounded metrics from actual result rows. Every value here
        comes from executed query data — nothing is invented."""
        metrics: list[Metric] = []
        for result in results:
            if not result.rows:
                continue
            first = result.rows[0]
            numeric_cols = [
                k for k, v in first.items()
                if isinstance(v, (int, float)) and not isinstance(v, bool)
            ]
            for col in numeric_cols:
                values = [
                    float(row[col]) for row in result.rows
                    if isinstance(row.get(col), (int, float))
                ]
                if not values:
                    continue
                source = result.sql[:80]
                if query_type == QueryType.KPI:
                    metrics.append(Metric(label=col, value=values[0], source=source))
                else:
                    # Don't prefix "total" onto columns that are already aggregates
                    lowered = col.lower()
                    is_aggregate = any(
                        lowered.startswith(p) for p in
                        ("avg", "average", "mean", "count", "rate", "ratio",
                         "pct", "percent", "share", "sum", "total", "median")
                    )
                    label = col if is_aggregate else f"total {col}"
                    metrics.append(Metric(label=label, value=sum(values), source=source))
                    if len(values) > 1:
                        metrics.append(Metric(label=f"latest {col}", value=values[-1], source=source))
        return metrics

    def build_answer(
        self,
        question: str,
        query_type: QueryType,
        metrics: list[Metric],
        sub_queries: list[SubQuery],
    ) -> GroundedAnswer:
        """Assemble the grounded answer text from real metrics only."""
        if not metrics:
            text = "The query returned data, but no numeric metrics were computed."
        elif query_type == QueryType.KPI:
            m = metrics[0]
            text = f"{_title(m.label)}: {_fmt(m.value)}"
        else:
            parts = [f"{_title(m.label)} {_fmt(m.value)}" for m in metrics]
            text = " | ".join(parts)
        return GroundedAnswer(
            text=text,
            query_type=query_type,
            metrics=metrics,
            sub_queries=sub_queries,
        )

    async def _run_single(self, question: str, schema, sample_text: str = "") -> QueryResult:
        """Generate + validate + execute one grounded query."""
        generated = await self.sql_agent.generate(
            question=question, schema=schema, sample_text=sample_text
        )
        validate_read_only(generated.sql)
        return await self.sql_agent.execute_query(generated.sql)

    # ------------------------------------------------------------------
    # Main pipeline
    # ------------------------------------------------------------------

    async def run(self, nl_query: str) -> AsyncIterator[dict[str, Any]]:
        """Orchestrate the full pipeline, yielding WebSocket-compatible events."""

        # 1. Cache check
        key = cache_key(self.connection_id, nl_query)
        cached = self.cache.get(key)
        if cached is not None:
            yield {"type": "progress", "message": "Cache hit — returning stored result"}
            query_type = self.infer_query_type(nl_query, cached)
            metrics = self.extract_metrics(query_type, [cached])
            answer = self.build_answer(nl_query, query_type, metrics, [])
            plan = self.viz_agent.plan_chart(nl_query, cached)
            chart_spec = self.viz_agent.build_vega_lite(plan, cached)
            yield {
                "type": "result",
                "chart_spec": chart_spec.model_dump(),
                "rows": cached.rows[:100],  # preview for table
                "row_count": cached.row_count,
                "sql": cached.sql,
                "execution_time_ms": cached.execution_time_ms,
                "query_type": query_type.value,
                "answer": answer.model_dump(),
                "cached": True,
            }
            return

        # 2. Schema introspection
        yield {"type": "progress", "message": "Analyzing database schema..."}
        schema = await self.schema_agent.fetch_schema()
        # Focus on the active table so the LLM doesn't wade through every
        # uploaded sample table in the demo database
        schema = schema.focused(self.focus_table)

        # 2b. Sample real rows so the planner/agent understand the data shape
        sample_text = ""
        if schema.tables:
            try:
                sample = await self.sql_agent.pool.get_sample(schema.tables[0], n=5)
                sample_text = _sample_text(schema.tables[0], sample)
            except Exception:
                sample_text = ""  # sampling is best-effort

        # 3. Query planning — decompose only genuinely complex questions
        # (deterministic classification first; the LLM planner is slow and
        # only worth it for multi-part questions)
        sub_queries: list[SubQuery] = []
        needs_decomposition = any(
            h in nl_query.lower() for h in ("compare", "vs ", "versus", "difference between", "and also", "plus ")
        )
        if self.planner is not None and needs_decomposition:
            try:
                sub_queries = await self.planner.decompose(
                    nl_query, schema.compact_repr(), sample_text
                )
            except Exception:
                sub_queries = []  # fall back to single query on planner failure

        results: list[QueryResult] = []
        sqls: list[str] = []

        if sub_queries:
            yield {
                "type": "progress",
                "message": f"Decomposed into {len(sub_queries)} sub-queries",
            }
            for sq in sub_queries:
                yield {"type": "progress", "message": f"Sub-query: {sq.question}"}
                try:
                    result = await self._run_single(sq.question, schema, sample_text)
                except Exception as e:
                    yield {"type": "progress", "message": f"Sub-query failed: {e}"}
                    continue
                if result.row_count > 0:
                    results.append(result)
                    sqls.append(result.sql)
            if not results:
                yield {"type": "error", "message": "All sub-queries returned zero rows. Try a broader question."}
                return
        else:
            yield {"type": "progress", "message": "Generating SQL query..."}
            generated = await self.sql_agent.generate(
                question=nl_query, schema=schema, sample_text=sample_text
            )
            sql = generated.sql
            validate_read_only(sql)
            yield {"type": "sql", "sql": sql}

            yield {"type": "progress", "message": "Executing query..."}
            result = await self.sql_agent.execute_query(sql)
            if result.row_count == 0:
                yield {"type": "error", "message": "Query returned zero rows. Try a broader question."}
                return
            results.append(result)
            sqls.append(sql)

        # 4. Grounded answer — every number comes from the executed results
        primary = results[-1]
        query_type = self.infer_query_type(nl_query, primary)
        metrics = self.extract_metrics(query_type, results)
        answer = self.build_answer(nl_query, query_type, metrics, sub_queries)

        # 5. Visualization of the primary result
        yield {"type": "progress", "message": "Building visualization..."}
        plan = self.viz_agent.plan_chart(nl_query, primary)
        chart_spec = self.viz_agent.build_vega_lite(plan, primary)

        # 6. Cache the primary result
        self.cache.put(key, primary)

        yield {
            "type": "result",
            "chart_spec": chart_spec.model_dump(),
            "rows": primary.rows[:100],  # preview for table
            "row_count": primary.row_count,
            "sql": primary.sql,
            "execution_time_ms": primary.execution_time_ms,
            "query_type": query_type.value,
            "answer": answer.model_dump(),
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