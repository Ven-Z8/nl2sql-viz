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

    def compact_repr(self) -> str:
        """Produce a compact text representation for LLM context."""
        lines: list[str] = []
        for table in self.tables:
            cols = self.columns.get(table, [])
            col_strs: list[str] = []
            for c in cols:
                if c.foreign_table and c.foreign_column:
                    tag = f" [FK→{c.foreign_table}.{c.foreign_column}]"
                elif c.constraint == "PRIMARY KEY":
                    tag = " [PK]"
                elif c.constraint:
                    tag = f" [{c.constraint}]"
                else:
                    tag = ""
                col_strs.append(f"{c.column}:{c.type}{tag}")
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
