"""CoordinatorAgent — orchestrates the full NL2SQL analytics pipeline.

NOOA Agent coordinating these stages:
1. Cache lookup (exact-key)
2. Schema introspection (SchemaAgent)
3. Schema linking via fast NLP classifier (SchemaLinker data + heuristics)
4. Complexity routing / query planning (QueryPlanner for complex questions)
5. SQL generation (SQLAgent)
6. Validation + cost gating (fail-closed) + execution
7. Grounded answer assembly (deterministic — every number from real data)
8. Chart hint selection (VizAgent) + caching

Streams progress events as an async generator for WebSocket delivery.
The ``type``/``stage`` strings below are a wire contract with the frontend —
change them only alongside frontend PipelinePanel/ArchitecturePanel.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

import sqlglot
from nooa import Agent
from sqlglot import exp

from app.agents.key_points import (
    KeyPointsAgent,
    filter_key_points_grounded,
    metrics_to_text,
    traceable_values,
)
from app.agents.planner import QueryPlanner
from app.agents.schema_agent import SchemaAgent
from app.agents.schema_linker import SchemaLinker
from app.agents.sql_agent import SQLAgent
from app.agents.viz_agent import VizAgent
from app.core.schema_validator import SchemaValidator
from app.db.guard import validate_read_only
from app.engine.cache import QueryCache, cache_key
from app.engine.nlp_classifier import get_classifier
from app.engine.schema_cache import get_schema_cache
from app.llm import SONNET
from app.models import (
    GeneratedSQL,
    GroundedAnswer,
    LinkedTable,
    Metric,
    ProvenanceEntry,
    QueryComplexity,
    QueryCost,
    QueryResult,
    QueryType,
    ReportSection,
    SubQuery,
)

logger = logging.getLogger(__name__)

_KPI_HINTS = ("how many", "total", "what is", "what's", "count of", "sum of", "average", "avg ")
_TREND_HINTS = ("over time", "trend", "monthly", "weekly", "daily", "quarterly", "by month", "by date", "by year")
_COMPARISON_HINTS = ("vs", "versus", "compare", "compared", "difference between")
_DISTRIBUTION_HINTS = ("distribution", "histogram", "spread of", "range of")

# Cost-gate ceiling (PostgreSQL EXPLAIN cost units). Override with MAX_COST env var.
MAX_COST = float(os.getenv("MAX_COST", "100000"))

# Wave 3 — self-correction budget: hard cap on executions per user query,
# shared across clarify / broaden / refine retries. The refine loop is the
# only stage that could spiral, so it is what enforces the ceiling.
_MAX_EXECUTIONS_PER_QUERY = 4
_MAX_REFINE_ITERATIONS = 2
_MIN_ROWS_FOR_STATS_SIGNALS = 3   # below this, null/uniform signals are noise
_NULL_MAX_RATIO = 0.8             # >80% NULLs in a column → null-dominant
_TOP_SEGMENTS = 5                 # segments enumerated for grouped answers
_LIMIT_CAP_MIN = 200              # tighten (a): never cap output below this
_OPTIONAL_JOIN_MARKER = "optional_join"  # planner comment marking droppable JOINs

_GROUP_BY_RE = re.compile(r"\bgroup\s+by\b", re.IGNORECASE)
_BREAKDOWN_RE = re.compile(r"\bby\s+[a-z_]+", re.IGNORECASE)
_AGG_CALL_RE = re.compile(r"\b(count|sum|avg|min|max)\s*\(", re.IGNORECASE)
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Callback the WebSocket layer injects so the pipeline can ask the user a
# clarifying question mid-run. Returns the chosen option index, or None on
# timeout / refusal — callers then proceed with their best-guess default.
AskUserFn = Callable[[str, list[str]], Awaitable[int | None]]

_BROADEN_FEEDBACK = (
    "The previous query returned zero rows. Rewrite it broader so it returns "
    "data: widen or drop date-range bounds, drop HAVING thresholds, and remove "
    "non-essential WHERE filters. KEEP the GROUP BY shape and the SELECT columns."
)

_DATE_FILTER_RE = re.compile(
    r"\b(between\s|::date\b|date_trunc\s*\(|extract\s*\(\s*(year|month|quarter)|"
    r"\d{4}-\d{2}-\d{2}|\b(?:19|20)\d{2}\b)",
    re.IGNORECASE,
)


def detect_relaxable_filters(sql: str) -> list[str]:
    """Name the non-essential filter families present in a zero-row query.

    Used purely for logging which filters the broadened retry relaxes.
    """
    relaxed: list[str] = []
    if re.search(r"\bhaving\b", sql, re.IGNORECASE):
        relaxed.append("HAVING threshold")
    if _DATE_FILTER_RE.search(sql):
        relaxed.append("date-range bounds")
    return relaxed


def ambiguous_focus_tables(linked_tables: list[str]) -> list[str]:
    """Tables whose names the question mentions verbatim.

    The linker only returns verbatim matches, so two or more of them means the
    focus-table intent is genuinely ambiguous — worth a clarify round instead
    of a guess. Order-preserving, capped at 4 options.
    """
    unique = list(dict.fromkeys(t for t in linked_tables if t))
    return unique[:4]


# ---------------------------------------------------------------------------
# Wave 3: result inspection (execute-inspect-refine)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ResultIssue:
    """One detected quality problem in a result set, with a fix hint."""

    code: str       # "empty" | "degenerate_aggregate" | "null_dominant" | "uniform_values"
    detail: str     # what was wrong, with specifics
    fix_hint: str   # how the regenerated SQL should change


@dataclass
class ResultInspection:
    """Outcome of inspecting one executed result set before synthesis."""

    issues: list[ResultIssue]

    @property
    def has_issues(self) -> bool:
        return bool(self.issues)

    def feedback(self) -> str:
        """Render the inspection report appended to the refine prompt."""
        lines = ["Previous attempt had result-quality problems:"]
        lines.extend(f"- {i.detail} — fix by: {i.fix_hint}" for i in self.issues)
        lines.append(
            "Return corrected SQL that answers the SAME question without "
            "these problems."
        )
        return "\n".join(lines)


def _question_wants_breakdown(question: str) -> bool:
    """Does the question ask for a comparison / breakdown / distribution?"""
    q = question.lower()
    return (
        _BREAKDOWN_RE.search(q) is not None
        or any(h in q for h in _COMPARISON_HINTS)
        or any(h in q for h in _DISTRIBUTION_HINTS)
    )


def inspect_result(question: str, sql: str, result: QueryResult) -> ResultInspection:
    """Inspect an executed result set for quality problems.

    Signals: zero rows surviving the retry ladder; a degenerate single-row
    overall aggregate when the question asks for a comparison/breakdown;
    NULL-dominant columns (>80% NULLs); suspiciously uniform numeric values.
    Pure function — no I/O, safe to unit test.
    """
    issues: list[ResultIssue] = []
    if result.row_count == 0:
        issues.append(ResultIssue(
            "empty",
            "it returned ZERO rows",
            "widen or drop date-range bounds, drop HAVING thresholds, and "
            "remove non-essential WHERE filters",
        ))
        return ResultInspection(issues)

    if (
        result.row_count == 1
        and _question_wants_breakdown(question)
        and _AGG_CALL_RE.search(sql)
        and not _GROUP_BY_RE.search(sql)
    ):
        issues.append(ResultIssue(
            "degenerate_aggregate",
            "it returned a single overall-aggregate row although the "
            "question asks for a comparison/breakdown",
            "add GROUP BY on the requested dimension and include it as a "
            "SELECT column",
        ))

    if len(result.rows) >= _MIN_ROWS_FOR_STATS_SIGNALS:
        total = len(result.rows)
        for col in list(result.rows[0].keys()):
            values = [row.get(col) for row in result.rows]
            present = [v for v in values if v is not None and v != ""]
            if len(present) / total < 1 - _NULL_MAX_RATIO:
                issues.append(ResultIssue(
                    "null_dominant",
                    f"column '{col}' is >{_NULL_MAX_RATIO:.0%} NULL across "
                    f"{total} rows",
                    f"coalesce or drop '{col}', or filter out rows where it "
                    f"is missing",
                ))
                continue
            numeric = [
                float(v) for v in present
                if isinstance(v, (int, float)) and not isinstance(v, bool)
            ]
            if len(numeric) == len(present) and len(set(numeric)) == 1:
                issues.append(ResultIssue(
                    "uniform_values",
                    f"column '{col}' has the same value ({numeric[0]:g}) in "
                    f"all {total} rows",
                    "verify the aggregation is not collapsing distinct groups",
                ))
    return ResultInspection(issues)


def _result_score(result: QueryResult) -> tuple[int, int]:
    """Ranking key for keep-the-better-result: non-empty beats empty; richer
    (more filled cells, capped) beats sparse. Ties prefer the earlier result."""
    if result.row_count == 0:
        return (0, 0)
    filled = sum(1 for row in result.rows for v in row.values() if v is not None)
    return (1, min(filled, 10_000))


# ---------------------------------------------------------------------------
# Wave 3: deterministic cost tightening
# ---------------------------------------------------------------------------

def tighten_limit_cap(sql: str, budget: float) -> tuple[str, str] | None:
    """Tighten (a): cap output rows with a LIMIT proportional to the budget.

    Halves an existing LIMIT when one is already present. Returns
    (tightened_sql, description), or None when the rewrite is impossible.
    """
    try:
        parsed = sqlglot.parse_one(sql, read="postgres")
    except Exception:
        return None
    cap = max(_LIMIT_CAP_MIN, int(budget // 100))
    existing = parsed.args.get("limit")
    if existing is not None:
        try:
            current = int(existing.expression.this)
        except Exception:
            return None
        halved = max(10, current // 2)
        if halved >= current:
            return None
        existing.set("expression", exp.Literal.number(halved))
        return parsed.sql(dialect="postgres"), f"capped LIMIT at {halved}"
    if not isinstance(parsed, exp.Select):
        return None  # unions / set operations are left to regeneration
    parsed = parsed.limit(cap)
    return parsed.sql(dialect="postgres"), f"capped output rows with LIMIT {cap}"


def tighten_date_range(sql: str) -> tuple[str, str] | None:
    """Tighten (b): narrow explicit BETWEEN windows to their most recent half.

    Deterministic — only ISO-date literals inside BETWEEN bounds move; each
    window start advances to the midpoint so the recent half is kept.
    """
    try:
        parsed = sqlglot.parse_one(sql, read="postgres")
    except Exception:
        return None
    changed = False
    for bt in parsed.find_all(exp.Between):
        low, high = bt.args.get("low"), bt.args.get("high")
        if not (
            low is not None and high is not None
            and getattr(low, "is_string", False)
            and getattr(high, "is_string", False)
        ):
            continue
        if not (_ISO_DATE_RE.match(str(low.this)) and _ISO_DATE_RE.match(str(high.this))):
            continue
        try:
            d_low = date.fromisoformat(str(low.this))
            d_high = date.fromisoformat(str(high.this))
        except ValueError:
            continue
        mid = d_low + (d_high - d_low) / 2
        if mid <= d_low:
            continue
        bt.set("low", exp.Literal.string(mid.isoformat()))
        changed = True
    if not changed:
        return None
    return (
        parsed.sql(dialect="postgres"),
        "narrowed BETWEEN date window to its recent half",
    )


def drop_optional_join(sql: str) -> tuple[str, str] | None:
    """Tighten (c): drop a JOIN the planner marked ``/* optional_join */``.

    Fires ONLY on that explicit marker comment — an unmarked join is
    load-bearing. The joined alias must be unreferenced after removal,
    otherwise the drop would orphan column references.
    """
    if _OPTIONAL_JOIN_MARKER not in sql:
        return None
    try:
        parsed = sqlglot.parse_one(sql, read="postgres")
    except Exception:
        return None
    for select in parsed.find_all(exp.Select):
        joins = select.args.get("joins") or []
        for j in joins:
            alias = getattr(j.this, "alias", "") or getattr(j.this, "name", "")
            if not alias:
                continue
            marked = any(
                _OPTIONAL_JOIN_MARKER in (c or "")
                for node in j.walk()
                for c in (node.comments or [])
            )
            if not marked:
                continue
            remaining = [x for x in joins if x is not j]
            select.set("joins", remaining or None)
            rendered = parsed.sql(dialect="postgres")
            if re.search(rf"\b{re.escape(alias)}\s*\.", rendered):
                return None  # still referenced — join is load-bearing after all
            return rendered, f"dropped planner-marked optional join on '{alias}'"
    return None


def tighten_sql(sql: str, attempt: int, budget: float) -> tuple[str, str] | None:
    """One automatic cost-tightening step for ``attempt`` (1-based).

    Attempt 1 caps rows via LIMIT; attempt 2 narrows date windows, falling
    back to dropping a planner-marked optional join when no dates exist.
    """
    if attempt == 1:
        return tighten_limit_cap(sql, budget)
    if attempt == 2:
        narrowed = tighten_date_range(sql)
        if narrowed is not None:
            return narrowed
        return drop_optional_join(sql)
    return None


# ---------------------------------------------------------------------------
# Wave 3: grouped-result presentation
# ---------------------------------------------------------------------------

def _is_grouped_result(sql: str, result: QueryResult) -> bool:
    """Grouped/multi-row shape: explicit GROUP BY, or multiple rows whose
    first column is categorical with several distinct values."""
    if result.row_count < 2 or not result.rows:
        return False
    if _GROUP_BY_RE.search(sql):
        return True
    first_col = list(result.rows[0].keys())[0]
    first_values = {row.get(first_col) for row in result.rows[:50]}
    return len(first_values) > 1 and any(isinstance(v, str) for v in first_values)


def _first_numeric_column(
    rows: list[dict[str, Any]], exclude: set[str]
) -> str | None:
    """First column whose sampled values are consistently numeric."""
    sample = rows[:20]
    for col in list(rows[0].keys()):
        if col in exclude:
            continue
        present = [row.get(col) for row in sample if row.get(col) is not None]
        if present and all(
            isinstance(v, (int, float)) and not isinstance(v, bool) for v in present
        ):
            return col
    return None


@dataclass
class MetricTrace:
    """Where one cited metric came from in the shipped ``queries`` array."""

    query_index: int
    row_index: int | None
    column: str


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


class _PipelineState:
    """Mutable per-query state threaded through the private stage methods."""

    def __init__(self, nl_query: str) -> None:
        self.nl_query = nl_query
        self.schema: Any = None            # scoped SchemaMap
        self.validator: SchemaValidator | None = None
        self.sample_text: str = ""
        self.complexity: QueryComplexity | None = None
        self.results: list[QueryResult] = []
        self.sqls: list[str] = []
        self.sections: list[ReportSection] = []
        self.linked_tables: list[str] = []  # tables the question names — ambiguity signal
        # Wave 3: executions for THIS user query, shared across clarify /
        # broaden / refine retries — never exceed _MAX_EXECUTIONS_PER_QUERY.
        self.executions = 0

    def ambiguous_tables(self) -> list[str]:
        """Focus-table candidates when the question names several."""
        return ambiguous_focus_tables(self.linked_tables)


class CoordinatorAgent(Agent, llm=SONNET):
    """You are the analytics coordinator for NL2SQL Viz.
    You orchestrate the full pipeline: schema → plan → SQL → execute → answer → visualize.

    You have access to:
    - self.schema_agent: SchemaAgent for database introspection
    - self.planner: QueryPlanner for decomposing complex questions
    - self.sql_agent: SQLAgent for SQL generation
    - self.viz_agent: VizAgent for chart-hint selection
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
    dsn: str = ""  # schema-cache key component; never leaves the server
    # Conversation context block for follow-up questions (Contract V3).
    # Empty on the stateless path — routing/linking behavior is unchanged.
    conversation_context: str = ""

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
        return self.extract_metrics_with_provenance(query_type, results)[0]

    def extract_metrics_with_provenance(
        self, query_type: QueryType, results: list[QueryResult]
    ) -> tuple[list[Metric], list[MetricTrace]]:
        """Extract grounded metrics plus their source traces.

        ``results`` must be in SHIPPED order — the same order as the result
        event's ``queries`` array (final query first) — so each trace's
        ``query_index`` is directly usable by clients.
        """
        metrics: list[Metric] = []
        traces: list[MetricTrace] = []
        seen: set[str] = set()

        def _append(label: str, value: float, source: str, trace: MetricTrace) -> None:
            """Append a metric, qualifying duplicate labels with a counter."""
            if label in seen:
                n = 2
                while f"{label} ({n})" in seen:
                    n += 1
                label = f"{label} ({n})"
            seen.add(label)
            metrics.append(Metric(label=label, value=value, source=source))
            traces.append(trace)

        for qi, result in enumerate(results):
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
                    _append(col, values[0], source, MetricTrace(qi, 0, col))
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
                        _append(col, sum(values) / len(values), source,
                                MetricTrace(qi, None, col))
                    else:
                        _append(f"total {col}", sum(values), source,
                                MetricTrace(qi, None, col))
                    if len(values) > 1:
                        _append(f"latest {col}", values[-1], source,
                                MetricTrace(qi, len(values) - 1, col))
        return metrics, traces

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

    def grounded_grouped_answer(
        self, shipped: list[QueryResult]
    ) -> tuple[list[Metric], list[MetricTrace], str] | None:
        """Enumerate top segments of a grouped result instead of KPI-style labels.

        The simple path used to slam the summary template onto GROUP BY
        results ("Total X 110 | Latest X 34") — misleading for segment
        breakdowns. Here the answer text enumerates the top segments with
        their ACTUAL shipped values, and every number carries a
        {query_index: 0, row_index: i} provenance trace into the primary
        result set (row_index = the row's original position). Returns None
        when the primary result is not grouped-shaped.
        """
        primary = shipped[0]
        if not _is_grouped_result(primary.sql, primary):
            return None
        dimension_col = list(primary.rows[0].keys())[0]
        value_col = _first_numeric_column(primary.rows, exclude={dimension_col})
        if value_col is None:
            return None
        order = sorted(
            range(len(primary.rows)),
            key=lambda i: -(primary.rows[i].get(value_col) or 0),
        )[:_TOP_SEGMENTS]
        parts: list[str] = []
        metrics: list[Metric] = []
        traces: list[MetricTrace] = []
        for i in order:
            dim_value = primary.rows[i].get(dimension_col)
            num_value = primary.rows[i].get(value_col)
            if not isinstance(num_value, (int, float)) or isinstance(num_value, bool):
                continue
            label = str(dim_value)
            parts.append(f"{label} {_fmt(float(num_value))}")
            metrics.append(Metric(label=label, value=float(num_value), source=primary.sql[:80]))
            traces.append(MetricTrace(query_index=0, row_index=i, column=value_col))
        if not metrics:
            return None
        text = f"{_title(value_col)} by {_title(dimension_col)}: " + ", ".join(parts)
        return metrics, traces, text

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

    def provenance_for_answer(
        self,
        answer: GroundedAnswer,
        traces: list[MetricTrace],
        shipped: list[QueryResult],
    ) -> list[dict[str, Any]] | None:
        """Wire-shape provenance for every number the answer cites.

        Combines the answer's KPI/summary metrics (traced at extraction time)
        with report-section metrics (each cites row 0 of its own result set,
        located here by SQL). Section numbers that cannot be located in a
        shipped result set are DROPPED from provenance.
        """
        entries: dict[tuple[str, float, int, int | None], ProvenanceEntry] = {}
        for m, t in zip(answer.metrics, traces):
            entries[(m.label, m.value, t.query_index, t.row_index)] = ProvenanceEntry(
                metric=m.label, value=m.value,
                query_index=t.query_index, row_index=t.row_index,
            )
        sql_to_index: dict[str, int] = {}
        for i, r in enumerate(shipped):
            sql_to_index.setdefault(r.sql[:80], i)
        for section in answer.sections:
            for m in section.metrics:
                qi = sql_to_index.get(m.source)
                if qi is None:
                    logger.warning("[PROVENANCE] Dropped untraceable section metric '%s'", m.label)
                    continue
                entries[(m.label, m.value, qi, 0)] = ProvenanceEntry(
                    metric=m.label, value=m.value, query_index=qi, row_index=0,
                )
        if not entries:
            return None
        return [e.model_dump() for e in entries.values()]

    async def _generate_sql(self, question: str, schema, sample_text: str = "", feedback: str = "") -> GeneratedSQL:
        """Generate SQL with timeout protection (30s max per call)."""
        t_start = time.perf_counter()
        try:
            generated = await asyncio.wait_for(
                self.sql_agent.generate_simple(
                    question=question, schema=schema, sample_text=sample_text, feedback=feedback
                ),
                timeout=30.0  # Hard 30s timeout per SQL generation call
            )
            t_elapsed = (time.perf_counter() - t_start) * 1000
            logger.debug("_generate_sql: %.0fms (feedback=%s)", t_elapsed, bool(feedback))
            return generated
        except asyncio.TimeoutError:
            logger.error("_generate_sql TIMEOUT after %.0fms", (time.perf_counter() - t_start) * 1000)
            raise TimeoutError(f"SQL generation timed out after 30s for: {question[:50]}...")

    async def _run_single(self, question: str, schema, sample_text: str = "") -> QueryResult:
        """Generate + validate + execute one grounded query."""
        generated = await self._generate_sql(question, schema, sample_text)
        validate_read_only(generated.sql)
        return await self.sql_agent.execute_query(generated.sql)

    # ------------------------------------------------------------------
    # Stage methods — each preserves its slice of the wire-event contract
    # ------------------------------------------------------------------

    async def _fetch_scoped_schema(self) -> tuple[Any, SchemaValidator]:
        """Introspect the DB and scope the schema to the active dataset graph.

        Introspection goes through the process-wide schema cache first —
        repeat queries on the same connection skip the ~18s round trip.
        """
        cache = get_schema_cache()
        full_schema = None
        if self.connection_id and self.dsn:
            full_schema = cache.get(self.connection_id, self.dsn)
        if full_schema is None:
            full_schema = await self.schema_agent.fetch_schema()
            if self.connection_id and self.dsn:
                cache.put(self.connection_id, self.dsn, full_schema)
        # The validator uses the FULL schema — joins need all tables' columns
        validator = SchemaValidator(full_schema)
        # Restrict to the FK-connected graph of the focus table so the linker
        # and SQL model never wade through every uploaded sample table.
        if self.focus_table:
            scope = full_schema.connected(self.focus_table)
        else:
            scope = full_schema.tables
        schema = full_schema.subschema(scope, first=self.focus_table)
        return schema, validator

    def schema_is_cached(self) -> bool:
        """Peek whether introspection would hit the schema cache (no fetch)."""
        if not (self.connection_id and self.dsn):
            return False
        return get_schema_cache().has(self.connection_id, self.dsn)

    async def _refocused_schema(
        self, chosen_table: str
    ) -> tuple[Any, SchemaValidator]:
        """Re-scope the schema to a user-chosen focus table (clarify path)."""
        previous = self.focus_table
        self.focus_table = chosen_table
        try:
            return await self._fetch_scoped_schema()
        finally:
            self.focus_table = previous

    async def _ask_focus_clarification(
        self, st: _PipelineState, ask_user: AskUserFn | None
    ) -> str | None:
        """Emit a clarify round when the question names several tables.

        Returns the chosen focus table, or None when there is no ambiguity,
        no channel to ask through, or the user timed out (120s, handled by
        the WebSocket layer) — callers then keep their best-guess default.
        """
        candidates = st.ambiguous_tables()
        if len(candidates) < 2 or ask_user is None:
            return None
        question = (
            "Your question mentions several tables "
            f"({', '.join(candidates)}). Which one should the analysis focus on?"
        )
        try:
            choice = await ask_user(question, candidates)
        except Exception as e:  # noqa: BLE001 — a broken clarify channel must not kill the query
            logger.warning("Clarify channel failed (%s) — proceeding with best guess", e)
            return None
        if choice is None or not 0 <= choice < len(candidates):
            logger.info("[CLARIFY] No usable answer (timeout/invalid) — proceeding with best guess")
            return None
        chosen = candidates[choice]
        logger.info("[CLARIFY] User chose focus table '%s'", chosen)
        return chosen

    async def _link_schema(self, st: _PipelineState) -> AsyncIterator[dict[str, Any]]:
        """NLP schema linking — filters the schema to tables the question mentions."""
        t_link_start = time.perf_counter()
        yield {"type": "progress", "stage": "link", "message": "Linking question to schema..."}

        classifier = get_classifier()
        schema_tables = list(st.schema.tables)
        schema_columns = {t: [c.column for c in st.schema.columns.get(t, [])] for t in st.schema.tables}
        entities = classifier.extract_entities(
            st.nl_query, schema_tables, schema_columns,
            context=self.conversation_context,
        )
        st.linked_tables = list(entities["tables"])

        if entities["tables"]:
            linked_tables = [
                LinkedTable(table=t, columns=schema_columns.get(t, []))
                for t in entities["tables"]
            ]
            st.schema = st.schema.filter_to(linked_tables)

        t_link_elapsed = time.perf_counter() - t_link_start
        yield {"type": "timing", "stage": "link", "elapsed_ms": round(t_link_elapsed * 1000)}

    async def _classify(self, st: _PipelineState) -> AsyncIterator[dict[str, Any]]:
        """Complexity routing via the fast NLP classifier."""
        t_complexity_start = time.perf_counter()
        classifier = get_classifier()
        complexity_label = classifier.classify_complexity(
            st.nl_query, list(st.schema.tables), context=self.conversation_context
        )
        st.complexity = QueryComplexity(complexity_label)
        t_complexity_elapsed = time.perf_counter() - t_complexity_start
        yield {
            "type": "timing",
            "stage": "complexity",
            "elapsed_ms": round(t_complexity_elapsed * 1000),
            "result": complexity_label,
        }

    async def _sample_rows(self, st: _PipelineState) -> str:
        """Sample real rows so the planner/agent understand the data shape."""
        if not st.schema.tables:
            return ""
        try:
            sample = await self.sql_agent.pool.get_sample(st.schema.tables[0], n=5)
            return _sample_text(st.schema.tables[0], sample)
        except Exception:
            return ""  # sampling is best-effort

    async def _gate_and_execute(
        self, st: _PipelineState, ask_user: AskUserFn | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        """Simple path: generate → validate → cost-gate → execute (+ recovery).

        Recovery on zero rows, in order: one clarify round when the question
        is ambiguous about its focus table, then ONE broadened retry that
        relaxes non-essential filters. Max 4 SQL generation calls otherwise.
        """
        nl_query = st.nl_query
        schema = st.schema
        sample_text = st.sample_text

        yield {"type": "progress", "stage": "generate", "message": "Generating SQL query..."}
        t_gen_start = time.perf_counter()
        generated = await self._generate_sql(nl_query, schema, sample_text)
        sql = generated.sql
        logger.debug("[TIMING] Initial SQL generation: %.0fms", (time.perf_counter() - t_gen_start) * 1000)

        # Validate: single retry if validation fails
        ok, fixed, errors = st.validator.validate_and_fix(sql)
        if not ok:
            logger.debug("[VALIDATE] First attempt failed: %s", errors[0][:60] if errors else "unknown")
            yield {"type": "progress", "stage": "validate", "message": f"Fixing query: {errors[0][:60] if errors else 'validation error'}"}
            t_retry = time.perf_counter()
            generated = await self._generate_sql(nl_query, schema, sample_text, feedback="; ".join(errors))
            sql = generated.sql
            logger.debug("[TIMING] Validation retry: %.0fms", (time.perf_counter() - t_retry) * 1000)
            ok, fixed, _ = st.validator.validate_and_fix(sql)
            if not ok:
                logger.error("SQL validation failed after retry: %s", "; ".join(errors)[:120])
                yield {"type": "error", "message": "SQL validation failed after retry"}
                return
        sql = fixed

        validate_read_only(sql)

        # Cost gate: fail-closed — an unavailable estimate blocks execution.
        allowed, reason, cost = await self._check_cost(sql)
        estimable = cost is not None and cost.estimated_cost > 0
        if not allowed and not estimable:
            # EXPLAIN itself failed — deterministic tightening cannot help;
            # keep the legacy single guided LLM retry, then fail closed.
            logger.warning("[COST] Query rejected (estimate unavailable): %s", reason[:120])
            yield {"type": "progress", "stage": "cost", "message": "Query too expensive — retrying with guidance"}
            t_cost_retry = time.perf_counter()
            generated = await self._generate_sql(nl_query, schema, sample_text, feedback=reason)
            sql = generated.sql
            logger.debug("[TIMING] Cost retry: %.0fms", (time.perf_counter() - t_cost_retry) * 1000)
            ok, fixed, _ = st.validator.validate_and_fix(sql)
            if ok:
                sql = fixed
            validate_read_only(sql)
            allowed, reason, _ = await self._check_cost(sql)
            if not allowed:
                # Fail-closed: refuse to execute a pathological query twice
                logger.error("[COST] Query still too expensive after retry: %s", reason[:120])
                yield {"type": "error", "message": f"Query blocked by cost limit — {reason}"}
                return
        elif not allowed:
            # Budget rejection — auto-tighten deterministically (Wave 3):
            # LIMIT cap, then date-range narrowing / planner-marked join drop.
            original_cost = cost.estimated_cost
            for attempt in (1, 2):
                tightened = tighten_sql(sql, attempt, MAX_COST)
                if tightened is None:
                    continue
                candidate, how = tightened
                yield {
                    "type": "progress",
                    "stage": "cost",
                    "message": f"Tightening query to fit budget (attempt {attempt})",
                }
                ok, fixed, _ = st.validator.validate_and_fix(candidate)
                if ok:
                    candidate = fixed
                validate_read_only(candidate)
                allowed, reason, cost = await self._check_cost(candidate)
                if allowed:
                    sql = candidate
                    logger.info("[COST][TIGHTEN] accepted after %s", how)
                    break
                sql = candidate  # stack tightenings for the next attempt
            if not allowed:
                logger.error(
                    "[COST] Still blocked after auto-tighten: est %.0f vs budget %.0f",
                    original_cost, MAX_COST,
                )
                yield {
                    "type": "error",
                    "message": (
                        f"Query blocked by cost limit — estimated cost "
                        f"{original_cost:,.0f} exceeds the budget of "
                        f"{MAX_COST:,.0f} even after automatic tightening "
                        f"(LIMIT cap, date-range narrowing). Narrow the "
                        f"question's date range, or ask for aggregated totals "
                        f"instead of row-level detail."
                    ),
                }
                return

        def _log_relaxed(original_sql: str) -> None:
            relaxed = detect_relaxable_filters(original_sql)
            logger.info("[ZERO-ROW][RELAX] broadened retry relaxes: %s",
                        ", ".join(relaxed) if relaxed else "restrictive WHERE filters")

        async def _generate_validated(feedback: str) -> str:
            """One generate→validate→read-only-check round."""
            generated = await self._generate_sql(nl_query, schema, sample_text, feedback=feedback)
            candidate = generated.sql
            ok, fixed, _ = st.validator.validate_and_fix(candidate)
            if ok:
                candidate = fixed
            validate_read_only(candidate)
            return candidate

        yield {"type": "sql", "sql": sql}

        # Execute
        yield {"type": "progress", "stage": "execute", "message": "Executing query..."}
        t_exec = time.perf_counter()
        result = await self.sql_agent.execute_query(sql)
        st.executions += 1
        logger.debug("[TIMING] Query execution: %.0fms, rows=%s", (time.perf_counter() - t_exec) * 1000, result.row_count)

        # Zero-row recovery — bounded to a clarify round + ONE broadened retry.
        if result.row_count == 0:
            # 1. Clarify: ambiguity about the focus table → ask, don't guess.
            chosen = await self._ask_focus_clarification(st, ask_user)
            if chosen is not None:
                yield {"type": "progress", "stage": "generate",
                       "message": f"Refocusing analysis on '{chosen}' and retrying..."}
                schema, validator = await self._refocused_schema(chosen)
                st.schema, st.validator = schema, validator
                sample_text = await self._sample_rows(st)
                focused = await _generate_validated(
                    f"The previous query returned zero rows because it targeted the wrong table. "
                    f"Focus the analysis on the '{chosen}' table."
                )
                allowed, reason = await self._cost_allowed(focused)
                if not allowed:
                    logger.error("[COST] Refocused retry rejected: %s", reason[:120])
                    yield {"type": "error", "message": f"Query blocked by cost limit — {reason}"}
                    return
                sql = focused
                yield {"type": "sql", "sql": sql}
                result = await self.sql_agent.execute_query(sql)
                st.executions += 1

            # 2. Broadened retry: relax non-essential filters once.
            if result.row_count == 0:
                logger.info("[ZERO-ROW] Retrying with broader query")
                _log_relaxed(sql)
                yield {"type": "progress", "stage": "execute", "message": "Query returned zero rows — retrying once with broader filters"}
                t_zero_retry = time.perf_counter()
                broadened = await _generate_validated(_BROADEN_FEEDBACK)
                logger.debug("[TIMING] Zero-row retry generation: %.0fms", (time.perf_counter() - t_zero_retry) * 1000)
                sql = broadened

                # The widened query must pass the cost gate too — before execution
                allowed, reason = await self._cost_allowed(sql)
                if not allowed:
                    logger.error("[COST] Widened zero-row retry rejected: %s", reason[:120])
                    yield {"type": "error", "message": f"Query blocked by cost limit — {reason}"}
                    return
                yield {"type": "sql", "sql": sql}

                t_exec2 = time.perf_counter()
                result = await self.sql_agent.execute_query(sql)
                st.executions += 1
                logger.debug("[TIMING] Zero-row retry execution: %.0fms, rows=%s", (time.perf_counter() - t_exec2) * 1000, result.row_count)

        # Wave 3: execute-inspect-refine — inspect result quality BEFORE
        # synthesis; regenerate with the inspection report at most
        # _MAX_REFINE_ITERATIONS times. The global execution budget (shared
        # with clarify/broaden above) is never exceeded, and the better
        # result set is kept (non-empty > richer > earlier).
        refinements = 0
        while (
            st.executions < _MAX_EXECUTIONS_PER_QUERY
            and refinements < _MAX_REFINE_ITERATIONS
        ):
            inspection = inspect_result(nl_query, sql, result)
            if not inspection.has_issues:
                break
            refinements += 1
            logger.info(
                "[REFINE] attempt %d/%d — %s",
                refinements,
                _MAX_REFINE_ITERATIONS,
                ", ".join(i.code for i in inspection.issues),
            )
            yield {
                "type": "progress",
                "stage": "refine",
                "message": f"Refining query (attempt {refinements} of {_MAX_REFINE_ITERATIONS})...",
            }
            refined = await _generate_validated(inspection.feedback())
            refined_allowed, refined_reason = await self._cost_allowed(refined)
            if not refined_allowed:
                logger.warning("[REFINE] Refined query rejected by cost gate: %s", refined_reason[:120])
                break  # keep the best result so far
            yield {"type": "sql", "sql": refined}
            candidate = await self.sql_agent.execute_query(refined)
            st.executions += 1
            if _result_score(candidate) > _result_score(result):
                sql, result = refined, candidate

        if result.row_count == 0:
            yield {"type": "error", "message": "Query returned zero rows. Try a broader question."}
            return

        st.results.append(result)
        st.sqls.append(sql)
        logger.debug("[TIMING] Simple path total: %.0fms", (time.perf_counter() - t_gen_start) * 1000)

    async def _plan_and_execute_complex(
        self, st: _PipelineState, ask_user: AskUserFn | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        """Complex path: plan sub-questions, parallel generation, gated parallel execution.

        On all-zero results: one clarify round when the focus table is
        ambiguous, then ONE broadened retry that relaxes non-essential filters.
        """
        nl_query = st.nl_query
        schema = st.schema
        sample_text = st.sample_text

        yield {"type": "progress", "stage": "plan", "message": "Planning multi-query analysis..."}
        try:
            sub_questions = await self.sql_agent.plan_analysis(nl_query, schema, sample_text)
        except Exception as e:
            # Small models can fail structured planning outright. Decomposition
            # is an enhancement, not a requirement — reroute to the simple
            # single-query path rather than killing the request.
            logger.warning("Plan stage failed (%s); rerouting to simple path", str(e)[:120])
            async for event in self._gate_and_execute(st, ask_user):
                yield event
            return
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
                ok, fixed, errors = st.validator.validate_and_fix(sqls[i])
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

        # Cost gate per sub-query — fail-closed: drop anything we cannot
        # prove cheap enough instead of executing it.
        runnable: list[tuple[int, str]] = []
        for i, sq in enumerate(sub_questions):
            allowed, reason = await self._cost_allowed(sqls[i])
            if not allowed:
                logger.warning("[COST] Query %d rejected: %s", i + 1, reason[:120])
                yield {"type": "progress", "stage": "cost", "message": f"Query {i+1} too expensive — retrying..."}
                try:
                    retry = await self.sql_agent.generate_simple(
                        question=sq.question, schema=schema,
                        sample_text=sample_text, feedback=reason,
                    )
                    sqls[i] = retry.sql
                except Exception as e:
                    logger.warning("Cost-gate regeneration failed: %s", e)
                    allowed = False
                else:
                    # Fail-closed: the replacement must pass the gate too
                    allowed, reason = await self._cost_allowed(sqls[i])
            if not allowed:
                yield {"type": "progress", "stage": "cost", "message": f"Query {i+1} dropped — {reason[:60]}"}
                continue
            runnable.append((i, sqls[i]))

        if not runnable:
            yield {"type": "error", "message": "All planned queries were blocked by the cost limit."}
            return

        async def _execute_round(pairs: list[tuple[int, str]]) -> list[dict[str, Any]]:
            """Execute pairs in parallel; append successes; return wire events."""
            events: list[dict[str, Any]] = [{
                "type": "progress", "stage": "execute",
                "message": f"Executing {len(pairs)} queries in parallel...",
            }]
            executed = await asyncio.gather(*[
                self.sql_agent.execute_query(sql) for _, sql in pairs
            ], return_exceptions=True)
            for pos, ((i, sql), result) in enumerate(zip(pairs, executed)):
                if isinstance(result, Exception):
                    events.append({"type": "progress", "stage": "execute", "message": f"Query {pos+1} failed: {result}"})
                    continue
                events.append({"type": "sql", "sql": sql})
                if result.row_count > 0:
                    st.results.append(result)
                    st.sections.append(self._section_from_result(
                        sub_questions[i].purpose or sub_questions[i].question, result))
            return events

        async def _regen_round(pairs: list[tuple[int, str]], feedback: str) -> list[tuple[int, str]]:
            """Regenerate + validate + cost-gate each sub-query against the
            CURRENT (possibly refocused) schema. Fail-closed per query."""
            regenerated: list[tuple[int, str]] = []
            for i, _old_sql in pairs:
                sq = sub_questions[i]
                try:
                    retry = await self.sql_agent.generate_simple(
                        question=sq.question, schema=st.schema,
                        sample_text=sample_text, feedback=feedback,
                    )
                except Exception as e:  # noqa: BLE001 — one bad regen must not kill the round
                    logger.warning("Regeneration failed for q%d: %s", i + 1, e)
                    continue
                candidate = retry.sql
                ok, fixed, _ = st.validator.validate_and_fix(candidate)
                if ok:
                    candidate = fixed
                validate_read_only(candidate)
                allowed, reason = await self._cost_allowed(candidate)
                if not allowed:
                    logger.warning("[COST] Regenerated q%d rejected: %s", i + 1, reason[:120])
                    continue
                regenerated.append((i, candidate))
            return regenerated

        # Execute all runnable queries IN PARALLEL
        for event in await _execute_round(runnable):
            yield event

        if not st.results:
            # 1. Clarify on focus-table ambiguity — ask rather than guess.
            chosen = await self._ask_focus_clarification(st, ask_user)
            if chosen is not None:
                schema, validator = await self._refocused_schema(chosen)
                st.schema, st.validator = schema, validator
                sample_text = await self._sample_rows(st)
                yield {"type": "progress", "stage": "generate",
                       "message": f"Refocusing analysis on '{chosen}' and retrying..."}
                refocused = await _regen_round(
                    runnable,
                    f"The previous queries returned zero rows because they targeted the wrong "
                    f"table. Focus the analysis on the '{chosen}' table.",
                )
                for event in await _execute_round(refocused):
                    yield event

        if not st.results:
            # 2. Broadened retry: relax non-essential filters ONCE, keep GROUP BY.
            relaxed = sorted({f for _, sql in runnable for f in detect_relaxable_filters(sql)})
            logger.info(
                "[ZERO-ROW][RELAX] All %d planned queries returned zero rows — broadening; relaxing: %s",
                len(runnable), ", ".join(relaxed) or "restrictive WHERE filters",
            )
            yield {"type": "progress", "stage": "execute",
                   "message": "Planned queries returned zero rows — broadening filters and retrying..."}
            broadened = await _regen_round(runnable, _BROADEN_FEEDBACK)
            for event in await _execute_round(broadened):
                yield event

        if not st.results:
            yield {"type": "error", "message": "All planned queries returned zero rows even after broadening. Try a broader question."}
            return

    async def _check_cost(self, sql: str) -> tuple[bool, str, QueryCost | None]:
        """Fail-closed cost gate returning the full estimate when available.

        Complements :meth:`_cost_allowed` for callers that need the estimated
        cost itself (actionable errors, auto-tightening). ``cost`` is None
        when EXPLAIN could not run at all; a cost with zero estimate marks an
        EXPLAIN failure reported through the fail-closed QueryCost path —
        either way deterministic tightening cannot help.
        """
        try:
            cost: QueryCost = await self.sql_agent.estimate_cost(sql)
        except Exception as e:
            logger.warning("Cost estimation failed (fail-closed): %s", e)
            return False, f"query cost could not be estimated ({e})", None
        if not cost.is_safe:
            return False, cost.reason, cost
        if cost.estimated_rows > 10_000_000:
            return False, (
                f"Query would scan ~{cost.estimated_rows:,.0f} rows "
                "(limit: 10,000,000). Add WHERE filters, GROUP BY, or LIMIT."
            ), cost
        if cost.estimated_cost > MAX_COST:
            return False, (
                f"estimated cost {cost.estimated_cost:,.0f} exceeds the "
                f"maximum budget of {MAX_COST:,.0f}. Add WHERE filters or LIMIT."
            ), cost
        return True, "", cost

    async def _cost_allowed(self, sql: str) -> tuple[bool, str]:
        """Fail-closed cost gate: compare the EXPLAIN estimate against limits.

        Returns (True, "") when the query is provably cheap, (False, reason)
        when the estimate is too high OR unavailable.
        """
        allowed, reason, _ = await self._check_cost(sql)
        return allowed, reason

    def _compose_answer(
        self, st: _PipelineState
    ) -> tuple[QueryType, list[Metric], list[MetricTrace], GroundedAnswer, QueryResult, list[QueryResult]]:
        """Grounded answer assembly — every number comes from executed results.

        Returns the query type, metrics + traces, the answer, the primary
        result, and the SHIPPED result list (final query first) that mirrors
        the wire ``queries`` array.
        """
        shipped = list(reversed(st.results))
        primary = shipped[0]
        query_type = self.infer_query_type(st.nl_query, primary)
        # Wave 3: grouped/multi-row results enumerate their top segments with
        # real values instead of wearing the KPI/summary template ("Total X …
        # | Latest X …"). Report sections (complex path) keep their format.
        grouped = None if st.sections else self.grounded_grouped_answer(shipped)
        if grouped is not None:
            metrics, traces, text = grouped
            answer = GroundedAnswer(text=text, query_type=query_type, metrics=metrics)
        else:
            metrics, traces = self.extract_metrics_with_provenance(query_type, shipped)
            answer = self.build_answer(st.nl_query, query_type, metrics, [])
            if st.sections:
                answer.sections = st.sections
                answer.text = f"Report: {st.nl_query}"
        return query_type, metrics, traces, answer, primary, shipped

    async def _compose_narrative(
        self,
        st: _PipelineState,
        answer: GroundedAnswer,
        metrics: list[Metric],
        traces: list[MetricTrace],
        primary: QueryResult,
        shipped: list[QueryResult],
    ) -> AsyncIterator[dict[str, Any]]:
        """Analyst narrative — key points synthesized ONLY from traceable numbers.

        The prompt offers each number tagged with its source id (``[q0.r2]``);
        after synthesis every cited number is verified against the shipped
        result sets and any point citing an untraceable figure is dropped.
        """
        if self.keypoints is None:
            return
        yield {"type": "progress", "stage": "narrative", "message": "Summarizing key points..."}
        try:
            tags = [
                f"[q{t.query_index}.r{t.row_index}]" if t.row_index is not None
                else f"[q{t.query_index}]"
                for t in traces
            ]
            points = await self.keypoints.synthesize(
                st.nl_query,
                metrics_to_text(metrics, answer.sections, primary.rows, metric_tags=tags),
            )
            grounded = filter_key_points_grounded(
                points, traceable_values(metrics, answer.sections,
                                         [row for r in shipped for row in r.rows])
            )
            dropped = len(points) - len(grounded)
            if dropped:
                logger.warning("[GROUNDEDNESS] Dropped %d key point(s) citing untraceable numbers", dropped)
            answer.key_points = grounded
        except Exception as e:
            logger.warning("Narrative synthesis skipped: %s", e)  # best-effort — numbers stay grounded

    def _build_chart_hint(
        self, question: str, result: QueryResult, query_type: QueryType
    ) -> dict[str, Any] | None:
        """Delegate deterministic chart selection to the VizAgent."""
        return self.viz_agent.build_chart_hint(question, result, query_type)

    def _cached_result_event(self, question: str, cached: QueryResult) -> dict[str, Any]:
        """Assemble the result payload served entirely from cache."""
        query_type = self.infer_query_type(question, cached)
        grouped = self.grounded_grouped_answer([cached])
        if grouped is not None:
            metrics, traces = grouped[0], grouped[1]
            answer = GroundedAnswer(text=grouped[2], query_type=query_type, metrics=metrics)
        else:
            metrics, traces = self.extract_metrics_with_provenance(query_type, [cached])
            answer = self.build_answer(question, query_type, metrics, [])
        chart_hint = self.viz_agent.build_chart_hint(question, cached, query_type)
        return {
            "type": "result",
            "query": question,
            "sql": cached.sql,
            "answer": answer.model_dump(),
            "rows": cached.rows[:100],  # preview for table
            "row_count": cached.row_count,
            "execution_time_ms": cached.execution_time_ms,
            "cached": True,
            "chart_hint": chart_hint,
            "queries": [{"sql": cached.sql, "row_count": cached.row_count}],
            "provenance": self.provenance_for_answer(answer, traces, [cached]),
        }

    # ------------------------------------------------------------------
    # Main pipeline
    # ------------------------------------------------------------------

    async def run(
        self, nl_query: str, ask_user: AskUserFn | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        """Orchestrate the full pipeline, yielding WebSocket-compatible events.

        ``ask_user`` (optional) lets the pipeline ask ONE clarifying question
        mid-run when focus-table intent is ambiguous. It returns the chosen
        option index or None (timeout/refusal) and the pipeline proceeds with
        its best-guess default.
        """
        t_total_start = time.perf_counter()
        logger.info("Pipeline start: %s", nl_query[:80])
        st = _PipelineState(nl_query)

        key = cache_key(self.connection_id, nl_query)
        cached = self.cache.get(key)
        if cached is not None:
            logger.info("Cache hit for: %s", nl_query[:80])
            yield {"type": "progress", "stage": "cache", "message": "Cache hit — returning stored result"}
            yield self._cached_result_event(nl_query, cached)
            return

        # 2. Schema introspection — cached connections skip the ~18s round trip
        schema_cached = self.schema_is_cached()
        yield {
            "type": "progress",
            "stage": "schema",
            "message": (
                "Using cached database schema — introspection skipped"
                if schema_cached else "Analyzing database schema..."
            ),
        }
        st.schema, st.validator = await self._fetch_scoped_schema()

        # 2b. Schema linking — fast entity extraction (50-100ms vs 5-10s LLM)
        async for event in self._link_schema(st):
            yield event

        # 2c. Sample real rows so the planner/agent understand the data shape
        st.sample_text = await self._sample_rows(st)

        # 3. Complexity routing — fast classifier (no LLM)
        async for event in self._classify(st):
            yield event

        if st.complexity == QueryComplexity.COMPLEX:
            async for event in self._plan_and_execute_complex(st, ask_user):
                yield event
        else:
            async for event in self._gate_and_execute(st, ask_user):
                yield event

        if not st.results:
            # A specific error event was already emitted by the failed path
            return

        # 4. Grounded answer — every number comes from the executed results
        query_type, metrics, traces, answer, primary, shipped = self._compose_answer(st)

        # 4a. Analyst narrative (grounded to shipped numbers only)
        async for event in self._compose_narrative(st, answer, metrics, traces, primary, shipped):
            yield event

        # 5. Visualization hint for the primary result
        yield {"type": "progress", "stage": "viz", "message": "Building visualization..."}
        chart_hint = self._build_chart_hint(nl_query, primary, query_type)

        # 6. Cache the primary result
        self.cache.put(key, primary)

        logger.info(
            "Pipeline done in %.0fms (%s rows)", (time.perf_counter() - t_total_start) * 1000, primary.row_count
        )
        yield {
            "type": "result",
            "query": nl_query,
            "sql": primary.sql,
            "answer": answer.model_dump(),
            "rows": primary.rows[:100],  # preview for table
            "row_count": primary.row_count,
            "execution_time_ms": primary.execution_time_ms,
            "cached": False,
            "chart_hint": chart_hint,
            "queries": [{"sql": r.sql, "row_count": r.row_count} for r in shipped],
            "provenance": self.provenance_for_answer(answer, traces, shipped),
        }
