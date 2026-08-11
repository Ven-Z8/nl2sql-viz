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

import asyncio
import re
from collections.abc import AsyncIterator
from typing import Any

from nooa import Agent, strategy
from nooa.config import CodeActConfig
from nooa.strategies import CodeActStrategy

from app.agents.planner import QueryPlanner
from app.agents.key_points import KeyPointsAgent, metrics_to_text
from app.agents.schema_agent import SchemaAgent
from app.agents.schema_linker import SchemaLinker
from app.agents.sql_agent import SQLAgent
from app.agents.viz_agent import VizAgent
from app.core.schema_validator import SchemaValidator
from app.db.guard import validate_read_only
from app.engine.cache import QueryCache, cache_key
from app.llm import SONNET
from app.models import (
    GeneratedSQL,
    GroundedAnswer,
    Metric,
    QueryComplexity,
    QueryResult,
    QueryType,
    ReportSection,
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
    linker: SchemaLinker | None = None
    keypoints: KeyPointsAgent | None = None
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
        seen: set[str] = set()

        def _append(label: str, value: float, source: str) -> None:
            """Append a metric, qualifying duplicate labels with a counter."""
            if label in seen:
                n = 2
                while f"{label} ({n})" in seen:
                    n += 1
                label = f"{label} ({n})"
            seen.add(label)
            metrics.append(Metric(label=label, value=value, source=source))

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
                    _append(col, values[0], source)
                else:
                    # Don't prefix "total" onto columns that are already aggregates
                    lowered = col.lower()
                    is_aggregate = any(
                        lowered.startswith(p) for p in
                        ("avg", "average", "mean", "count", "rate", "ratio",
                         "pct", "percent", "share", "sum", "total", "median")
                    )
                    if is_aggregate:
                        # Summing per-group averages is meaningless — the
                        # summary of an aggregate column is its mean
                        _append(col, sum(values) / len(values), source)
                    else:
                        _append(f"total {col}", sum(values), source)
                    if len(values) > 1:
                        _append(f"latest {col}", values[-1], source)
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

    def _section_from_result(self, title: str, result: QueryResult) -> ReportSection:
        """Build a report section from one query's grounded result."""
        metrics: list[Metric] = []
        if result.rows:
            first = result.rows[0]
            for col, val in first.items():
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    metrics.append(Metric(label=col, value=float(val), source=result.sql[:80]))
        text = f"{title}: {result.row_count} rows"
        if result.rows:
            text = f"{title}: " + "; ".join(
                f"{k}={v}" for k, v in list(result.rows[0].items())[:4]
            )
        return ReportSection(title=title, text=text, metrics=metrics)

    async def _generate_sql(self, question: str, schema, sample_text: str = "", feedback: str = "") -> GeneratedSQL:
        """Classify complexity and route: simple → Predict, complex → CodeAct."""
        try:
            complexity = await self.sql_agent.classify_complexity(
                question, schema.compact_repr()
            )
        except Exception:
            complexity = QueryComplexity.SIMPLE  # fall back to the fast path
        if complexity == QueryComplexity.COMPLEX:
            return await self.sql_agent.generate_complex(
                question=question, schema=schema, sample_text=sample_text
            )
        return await self.sql_agent.generate_simple(
            question=question, schema=schema, sample_text=sample_text, feedback=feedback
        )

    async def _run_single(self, question: str, schema, sample_text: str = "") -> QueryResult:
        """Generate + validate + execute one grounded query."""
        generated = await self._generate_sql(question, schema, sample_text)
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
            yield {"type": "progress", "stage": "cache", "message": "Cache hit — returning stored result"}
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
        yield {"type": "progress", "stage": "schema", "message": "Analyzing database schema..."}
        full_schema = await self.schema_agent.fetch_schema()
        # The validator uses the FULL schema — joins need all tables' columns
        validator = SchemaValidator(full_schema)

        # 2a. Restrict to the active dataset — the FK-connected graph of the
        # focus table — so the linker and SQL model never wade through every
        # uploaded sample table in the demo database.
        if self.focus_table:
            scope = full_schema.connected(self.focus_table)
        else:
            scope = full_schema.tables
        schema = full_schema.subschema(scope, first=self.focus_table)

        # 2b. Schema linking — a fast model grounds the question in the real
        # schema: it picks the relevant tables/columns so the SQL model never
        # guesses across the whole database.
        if self.linker is not None:
            try:
                yield {"type": "progress", "stage": "link", "message": "Linking question to schema..."}
                linked = await self.linker.link(nl_query, schema.compact_repr())
                if linked:
                    schema = schema.filter_to(linked)
            except Exception:
                pass  # fall back to the dataset schema on linker failure

        # 2c. Sample real rows so the planner/agent understand the data shape
        sample_text = ""
        if schema.tables:
            try:
                sample = await self.sql_agent.pool.get_sample(schema.tables[0], n=5)
                sample_text = _sample_text(schema.tables[0], sample)
            except Exception:
                sample_text = ""  # sampling is best-effort

        # 3. Complexity routing — simple → single query, complex → multi-query plan + report
        complexity = QueryComplexity.SIMPLE
        try:
            complexity = await self.sql_agent.classify_complexity(
                nl_query, schema.compact_repr()
            )
        except Exception:
            complexity = QueryComplexity.SIMPLE

        results: list[QueryResult] = []
        sqls: list[str] = []
        report_sections: list[ReportSection] = []

        if complexity == QueryComplexity.COMPLEX:
            yield {"type": "progress", "stage": "plan", "message": "Planning multi-query analysis..."}
            sub_questions = await self.sql_agent.plan_analysis(nl_query, schema, sample_text)
            if not sub_questions:
                sub_questions = [SubQuery(id="q1", question=nl_query, purpose="main analysis")]

            # Generate each sub-query's SQL IN PARALLEL — the model is the
            # bottleneck, so concurrent calls cut wall time dramatically.
            yield {"type": "progress", "stage": "generate", "message": f"Generating {len(sub_questions)} queries in parallel..."}
            generated = await asyncio.gather(*[
                self.sql_agent.generate_simple(
                    question=sq.question, schema=schema, sample_text=sample_text
                )
                for sq in sub_questions
            ])

            # Validate each query against the real schema — no guessing.
            # Retry with feedback if the model used a wrong column.
            sqls = [g.sql for g in generated]
            for i in range(len(sqls)):
                for attempt in range(2):
                    ok, fixed, errors = validator.validate_and_fix(sqls[i])
                    if ok:
                        sqls[i] = fixed
                        break
                    feedback = "; ".join(errors)
                    yield {"type": "progress", "stage": "validate", "message": f"Fixing query {i+1}: {errors[0][:60]}"}
                    retry = await self.sql_agent.generate_simple(
                        question=sub_questions[i].question, schema=schema,
                        sample_text=sample_text, feedback=feedback,
                    )
                    sqls[i] = retry.sql
                # Cost gate per sub-query — drop pathological queries
                try:
                    cost = await self.sql_agent.estimate_cost(sqls[i])
                    if not cost.is_safe:
                        yield {"type": "progress", "stage": "cost", "message": f"Query {i+1} too expensive — retrying..."}
                        retry = await self.sql_agent.generate_simple(
                            question=sub_questions[i].question, schema=schema,
                            sample_text=sample_text, feedback=cost.reason,
                        )
                        sqls[i] = retry.sql
                except Exception:
                    pass  # EXPLAIN is best-effort

            # Execute all queries IN PARALLEL
            yield {"type": "progress", "stage": "execute", "message": f"Executing {len(sqls)} queries in parallel..."}
            executed = await asyncio.gather(*[
                self.sql_agent.execute_query(sql) for sql in sqls
            ], return_exceptions=True)

            for i, (sq, sql, result) in enumerate(zip(sub_questions, sqls, executed)):
                if isinstance(result, Exception):
                    yield {"type": "progress", "stage": "execute", "message": f"Query {i+1} failed: {result}"}
                    continue
                yield {"type": "sql", "sql": sql}
                if result.row_count > 0:
                    results.append(result)
                    report_sections.append(self._section_from_result(sq.purpose or sq.question, result))
            if not results:
                yield {"type": "error", "message": "All planned queries returned zero rows. Try a broader question."}
                return
        else:
            yield {"type": "progress", "stage": "generate", "message": "Generating SQL query..."}
            generated = await self._generate_sql(nl_query, schema, sample_text)
            sql = generated.sql
            # Validate against the real schema — no guessing. Retry with
            # feedback if the model used a wrong column.
            for attempt in range(2):
                ok, fixed, errors = validator.validate_and_fix(sql)
                if ok:
                    sql = fixed
                    break
                feedback = "; ".join(errors)
                yield {"type": "progress", "stage": "validate", "message": f"Fixing query: {errors[0][:60]}"}
                generated = await self._generate_sql(
                    nl_query, schema, sample_text, feedback=feedback
                )
                sql = generated.sql
            validate_read_only(sql)
            yield {"type": "sql", "sql": sql}

            # Cost gate — reject pathological queries (full scans of huge
            # tables, cartesian joins) BEFORE they burn the query budget.
            try:
                cost = await self.sql_agent.estimate_cost(sql)
                if not cost.is_safe:
                    yield {"type": "progress", "stage": "cost", "message": f"Query too expensive ({cost.reason[:70]}) — retrying..."}
                    generated = await self._generate_sql(
                        nl_query, schema, sample_text, feedback=cost.reason
                    )
                    sql = generated.sql
                    for attempt in range(2):
                        ok, fixed, errors = validator.validate_and_fix(sql)
                        if ok:
                            sql = fixed
                            break
                        feedback = "; ".join(errors)
                        generated = await self._generate_sql(
                            nl_query, schema, sample_text, feedback=feedback
                        )
                        sql = generated.sql
                    validate_read_only(sql)
                    yield {"type": "sql", "sql": sql}
            except Exception:
                pass  # EXPLAIN is best-effort — execute anyway

            yield {"type": "progress", "stage": "execute", "message": "Executing query..."}
            result = await self.sql_agent.execute_query(sql)
            if result.row_count == 0:
                # Zero-row dead-end: retry once asking the model to broaden the
                # query (drop restrictive filters), so the user doesn't hit a
                # wall on a question where the answer clearly exists.
                yield {"type": "progress", "stage": "execute", "message": "Query returned zero rows — retrying with a broader query..."}
                generated = await self._generate_sql(
                    nl_query, schema, sample_text,
                    feedback="The previous query returned zero rows. Remove restrictive filters, widen any date/status conditions, and make sure the query returns data.",
                )
                sql = generated.sql
                for attempt in range(2):
                    ok, fixed, errors = validator.validate_and_fix(sql)
                    if ok:
                        sql = fixed
                        break
                    feedback = "; ".join(errors)
                    generated = await self._generate_sql(
                        nl_query, schema, sample_text, feedback=feedback
                    )
                    sql = generated.sql
                validate_read_only(sql)
                yield {"type": "sql", "sql": sql}
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
        answer = self.build_answer(nl_query, query_type, metrics, [])
        if report_sections:
            answer.sections = report_sections
            answer.text = f"Report: {nl_query}"

        # 4a. Analyst narrative — key points synthesized ONLY from the
        # grounded numbers, so the answer tells a story instead of a bare dump
        if self.keypoints is not None:
            try:
                yield {"type": "progress", "stage": "narrative", "message": "Summarizing key points..."}
                answer.key_points = await self.keypoints.synthesize(
                    nl_query, metrics_to_text(metrics, answer.sections, primary.rows)
                )
            except Exception:
                pass  # narrative is best-effort — numbers stay grounded

        # 5. Visualization of the primary result
        yield {"type": "progress", "stage": "viz", "message": "Building visualization..."}
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