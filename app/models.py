"""Pydantic models for NOOA agent typed I/O contracts.

These models define the data structures that flow between agents.
NOOA uses them for:
- Pass-by-reference rendering (bounded previews in LLM context)
- Return type validation (PredictStrategy validates against these)
- Context rendering (pprint produces bounded previews)
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Schema models
# ---------------------------------------------------------------------------

class ColumnInfo(BaseModel):
    """A single column in a database table."""
    column: str
    type: str
    nullable: bool = False
    constraint: str | None = None
    foreign_table: str | None = None
    foreign_column: str | None = None


class SchemaMap(BaseModel):
    """Compact schema representation for LLM context.

    Designed to fit within context window limits even for large databases.
    """
    tables: list[str]
    columns: dict[str, list[ColumnInfo]]
    row_estimates: dict[str, int] = Field(
        default_factory=dict,
        description="Approximate row counts from pg_stat_user_tables",
    )
    indexes: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Index names per table",
    )

    def filter_to(self, linked: list[LinkedTable]) -> "SchemaMap":
        """Return a schema containing only the linked tables and columns.

        Used after schema linking — the SQL model generates against a small,
        correct context instead of the full schema.
        """
        if not linked:
            return self
        tables: list[str] = []
        columns: dict[str, list[ColumnInfo]] = {}
        for lt in linked:
            if lt.table not in self.columns:
                continue
            tables.append(lt.table)
            all_cols = {c.column: c for c in self.columns[lt.table]}
            wanted = [c for c in lt.columns if c in all_cols]
            # Always include join keys (FK columns) and primary keys so joins work
            for c in self.columns[lt.table]:
                if c.column in wanted:
                    continue
                if c.foreign_table or c.constraint == "PRIMARY KEY":
                    wanted.append(c.column)
            columns[lt.table] = [all_cols[c] for c in wanted]
        return SchemaMap(
            tables=tables,
            columns=columns,
            row_estimates={t: self.row_estimates.get(t, 0) for t in tables},
            indexes={t: self.indexes.get(t, []) for t in tables},
        )

    def connected(self, root: str) -> list[str]:
        """Tables reachable from ``root`` via foreign keys — the dataset graph.

        A relational dataset is exactly the FK-connected component of its
        tables, so this isolates the selected dataset from unrelated tables
        (e.g. other datasets or uploaded samples in the same database).
        """
        if root not in self.columns:
            return [root]
        graph: dict[str, set[str]] = {t: set() for t in self.tables}
        for t in self.tables:
            for c in self.columns.get(t, []):
                if c.foreign_table and c.foreign_table in graph:
                    graph[t].add(c.foreign_table)
                    graph[c.foreign_table].add(t)
        seen: set[str] = set()
        stack = [root]
        while stack:
            t = stack.pop()
            if t in seen:
                continue
            seen.add(t)
            stack.extend(graph[t] - seen)
        return [t for t in self.tables if t in seen]

    def subschema(self, tables: list[str], first: str | None = None) -> "SchemaMap":
        """Return a schema with full columns for exactly ``tables``.

        ``first`` (e.g. the focus table) is moved to the front of the list.
        """
        keep = [t for t in tables if t in self.columns]
        if first and first in keep:
            keep = [first] + [t for t in keep if t != first]
        return SchemaMap(
            tables=keep,
            columns={t: self.columns[t] for t in keep},
            row_estimates={t: self.row_estimates.get(t, 0) for t in keep},
            indexes={t: self.indexes.get(t, []) for t in keep},
        )

    def focused(self, focus_table: str | None) -> "SchemaMap":
        """Return a schema focused on one table — its columns in full, other
        tables listed by name only. Keeps the LLM context small when the
        database has many tables (e.g. all uploaded samples)."""
        if not focus_table or focus_table not in self.tables:
            return self
        focused_columns = {focus_table: self.columns.get(focus_table, [])}
        other_tables = [t for t in self.tables if t != focus_table]
        return SchemaMap(
            tables=[focus_table] + other_tables,
            columns=focused_columns,
            row_estimates={t: self.row_estimates.get(t, 0) for t in [focus_table] + other_tables},
            indexes={t: self.indexes.get(t, []) for t in [focus_table] + other_tables},
        )

    def compact_repr(self, max_columns: int = 40) -> str:
        """Produce a compact text representation for LLM context.

        Wide tables (e.g. 150-column financial datasets) are truncated to
        ``max_columns`` per table so the prompt stays fast — the LLM can
        still query any column, it just doesn't see all of them upfront.
        """
        lines: list[str] = []
        for table in self.tables:
            cols = self.columns.get(table, [])
            col_strs: list[str] = []
            for c in cols[:max_columns]:
                if c.foreign_table and c.foreign_column:
                    tag = f" [FK→{c.foreign_table}.{c.foreign_column}]"
                elif c.constraint == "PRIMARY KEY":
                    tag = " [PK]"
                elif c.constraint:
                    tag = f" [{c.constraint}]"
                else:
                    tag = ""
                col_strs.append(f"{c.column}:{c.type}{tag}")
            if len(cols) > max_columns:
                col_strs.append(f"...and {len(cols) - max_columns} more columns")
            rows = self.row_estimates.get(table, 0)
            lines.append(f"{table}(~{rows:,} rows)({', '.join(col_strs)})")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Query models
# ---------------------------------------------------------------------------

class QueryComplexity(str, Enum):
    """How complex is the natural language question?"""
    SIMPLE = "simple"        # single table, basic aggregation
    MODERATE = "moderate"    # joins, window functions
    COMPLEX = "complex"      # multi-step, cross-table analysis


class QueryCost(BaseModel):
    """Pre-execution cost estimate from EXPLAIN."""
    estimated_rows: float = Field(description="Estimated rows scanned")
    estimated_cost: float = Field(description="PostgreSQL cost units")
    scan_type: str = Field(default="Seq Scan", description="Primary scan node type")
    tables_touched: list[str] = Field(default_factory=list)
    is_safe: bool = Field(default=True, description="Whether the query passes cost gates")
    reason: str = Field(default="OK", description="Rejection reason if not safe")


class GeneratedSQL(BaseModel):
    """Validated SQL output from the SQLAgent."""
    sql: str
    explanation: str = Field(default="", description="Brief explanation of the query logic")
    complexity: QueryComplexity = QueryComplexity.SIMPLE
    cost: QueryCost | None = None
    attempts: int = Field(default=1, description="Number of generation attempts")


class QueryResult(BaseModel):
    """Result from a database query execution."""
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool = False
    execution_time_ms: float = 0.0
    sql: str = ""

    def sample(self, n: int = 5) -> list[dict[str, Any]]:
        """Return head+tail sample for bounded preview."""
        if len(self.rows) <= n * 2:
            return self.rows
        return self.rows[:n] + self.rows[-n:]


# ---------------------------------------------------------------------------
# Visualization models
# ---------------------------------------------------------------------------

class ChartType(str, Enum):
    BAR = "bar"
    LINE = "line"
    SCATTER = "scatter"
    ARC = "arc"
    HEATMAP = "heatmap"
    SUMMARY = "summary"


class DataStrategy(str, Enum):
    """How the chart data is delivered to the frontend."""
    INLINE = "inline"        # Full data in spec (≤50K rows)
    SAMPLED = "sampled"      # Server-side downsampled
    AGGREGATED = "aggregated"  # Re-aggregated server-side
    TILED = "tiled"          # Progressive tile-based loading


class ChartPlan(BaseModel):
    """Decision about what chart to create."""
    chart_type: ChartType
    data_strategy: DataStrategy
    title: str
    x_field: str = ""
    y_field: str = ""
    color_field: str = ""


class ChartSpec(BaseModel):
    """Validated chart specification ready for frontend rendering."""
    renderer: str = Field(description="'vega-lite' or 'echarts'")
    spec: dict[str, Any] = Field(description="The chart spec (Vega-Lite JSON or ECharts option)")
    plan: ChartPlan
    row_count: int = 0


# ---------------------------------------------------------------------------
# Grounded answer models
# ---------------------------------------------------------------------------

class QueryType(str, Enum):
    """What kind of question is being asked — drives the UI layout."""
    KPI = "kpi"                # "how many X" / "what is the total Y" — stat strip
    TREND = "trend"            # "over time" — time series chart
    COMPARISON = "comparison"  # "vs", "by segment" — grouped bar
    BREAKDOWN = "breakdown"    # "by category" — bar / pie
    DISTRIBUTION = "distribution"  # "distribution of" — histogram


class SubQuery(BaseModel):
    """A decomposed sub-question of a complex query."""
    id: str
    question: str
    purpose: str = Field(default="", description="Why this sub-query is needed")


class LinkedTable(BaseModel):
    """A table and the columns relevant to a question (schema linking)."""
    table: str
    columns: list[str]


class PlannedQuery(BaseModel):
    """A single SQL query in a multi-query plan for a complex question."""
    id: str
    sql: str
    purpose: str = Field(default="", description="What this query computes")


class QueryPlan(BaseModel):
    """A plan of 3-5 SQL queries that together answer a complex question."""
    queries: list[PlannedQuery]
    summary: str = Field(default="", description="How the queries combine into the answer")


class ReportSection(BaseModel):
    """One section of a synthesized report."""
    title: str
    text: str
    metrics: list[Metric] = Field(default_factory=list)


class Metric(BaseModel):
    """A single grounded number — always computed from query results."""
    label: str
    value: float
    unit: str = ""
    source: str = Field(default="", description="Which sub-query / row produced this value")


class GroundedAnswer(BaseModel):
    """The final answer — every number traces back to executed query results."""
    text: str
    query_type: QueryType = QueryType.KPI
    metrics: list[Metric] = Field(default_factory=list)
    sub_queries: list[SubQuery] = Field(default_factory=list)
    sections: list[ReportSection] = Field(default_factory=list)
    key_points: list[str] = Field(
        default_factory=list,
        description="Analyst-style insights synthesized ONLY from the grounded metrics",
    )
