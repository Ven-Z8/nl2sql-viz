"""Unit tests for groundedness: provenance extraction + queries array (Contract V2).

Every number cited in an answer must map to a (query_index, row_index) inside
the result event's ``queries`` array; numbers that cannot be traced are dropped
rather than invented.
"""
import asyncio

from app.agents.coordinator import CoordinatorAgent
from app.agents.key_points import (
    extract_numbers,
    filter_key_points_grounded,
    metrics_to_text,
    traceable_values,
)
from app.agents.viz_agent import VizAgent
from app.engine.cache import QueryCache, cache_key
from app.models import (
    ColumnInfo,
    GeneratedSQL,
    GroundedAnswer,
    Metric,
    QueryCost,
    QueryResult,
    QueryType,
    ReportSection,
    SchemaMap,
)


def _make_coordinator() -> CoordinatorAgent:
    agent = CoordinatorAgent()
    agent.viz_agent = VizAgent()
    agent.cache = QueryCache()
    agent.connection_id = "prov-test"  # no dsn → schema cache bypassed
    return agent


class StubSQL:
    """Single query, single result — enough for the simple path."""

    def __init__(self, result: QueryResult) -> None:
        self.result = result

    async def estimate_cost(self, sql):
        return QueryCost(estimated_rows=10, estimated_cost=10, is_safe=True)

    async def generate_simple(self, question, schema, sample_text="", feedback=""):
        return GeneratedSQL(sql=self.result.sql)

    async def execute_query(self, sql):
        return self.result


class StubViz:
    def build_chart_hint(self, question, result, query_type=None):
        return VizAgent().build_chart_hint(question, result, query_type)


def _stub_schema() -> SchemaMap:
    return SchemaMap(
        tables=["accounts"],
        columns={"accounts": [
            ColumnInfo(column="region", type="text"),
            ColumnInfo(column="sales", type="numeric"),
        ]},
    )


# ---------------------------------------------------------------------------
# extract_metrics_with_provenance — numbers map to (query_index, row_index)
# ---------------------------------------------------------------------------

def test_kpi_metric_maps_to_first_row_of_query_zero():
    agent = _make_coordinator()
    result = QueryResult(
        columns=["count"], rows=[{"count": 42}], row_count=1,
        sql="SELECT count(*) AS count FROM accounts",
    )
    metrics, traces = agent.extract_metrics_with_provenance(QueryType.KPI, [result])
    assert [(m.label, m.value) for m in metrics] == [("count", 42.0)]
    assert [(t.query_index, t.row_index, t.column) for t in traces] == [(0, 0, "count")]


def test_breakdown_metrics_map_to_rows_and_derived_cells():
    agent = _make_coordinator()
    result = QueryResult(
        columns=["month", "sales"],
        rows=[{"month": "2024-01", "sales": 100}, {"month": "2024-02", "sales": 200}],
        row_count=2,
        sql="SELECT month, sales FROM accounts",
    )
    metrics, traces = agent.extract_metrics_with_provenance(QueryType.BREAKDOWN, [result])
    by_label = {m.label: (m, t) for m, t in zip(metrics, traces)}
    # "total sales" sums across rows → row_index None
    assert by_label["total sales"][1].query_index == 0
    assert by_label["total sales"][1].row_index is None
    assert by_label["total sales"][1].column == "sales"
    # "latest sales" cites the last contributing row
    assert by_label["latest sales"][0].value == 200.0
    assert by_label["latest sales"][1].row_index == 1


def test_multi_result_traces_use_shipped_order():
    agent = _make_coordinator()
    r_a = QueryResult(columns=["v"], rows=[{"v": 1}], row_count=1, sql="SELECT 1 AS v")
    r_b = QueryResult(columns=["w"], rows=[{"w": 2}], row_count=1, sql="SELECT 2 AS w")
    # Passed in SHIPPED order (final query first)
    _, traces = agent.extract_metrics_with_provenance(QueryType.KPI, [r_b, r_a])
    assert traces[0].query_index == 0 and traces[0].column == "w"
    assert traces[1].query_index == 1 and traces[1].column == "v"


def test_provenance_for_answer_drops_untraceable_section_metrics():
    agent = _make_coordinator()
    shipped = [
        QueryResult(columns=["a"], rows=[{"a": 5}], row_count=1, sql="SELECT 5 AS a"),
    ]
    orphan_sql = "SELECT secret FROM hidden_table"
    answer = GroundedAnswer(
        text="Report",
        metrics=[Metric(label="a", value=5)],
        sections=[ReportSection(
            title="ghost",
            text="ghost: x=99",
            metrics=[Metric(label="x", value=99, source=orphan_sql[:80])],
        )],
    )
    traces = agent.extract_metrics_with_provenance(QueryType.KPI, shipped)[1]
    prov = agent.provenance_for_answer(answer, traces, shipped)
    assert prov is not None
    assert prov == [
        {"metric": "a", "value": 5.0, "query_index": 0, "row_index": 0}
    ]


def test_provenance_none_when_no_traceable_numbers():
    agent = _make_coordinator()
    answer = GroundedAnswer(text="nothing numeric")
    assert agent.provenance_for_answer(answer, [], []) is None


# ---------------------------------------------------------------------------
# End-to-end payload: result event gains queries[] + provenance[]
# ---------------------------------------------------------------------------

def test_result_event_carries_queries_and_provenance():
    agent = _make_coordinator()

    class StubSchema:
        async def fetch_schema(self):
            return _stub_schema()

    result = QueryResult(
        columns=["region", "sales"],
        rows=[{"region": "North", "sales": 120}],
        row_count=1,
        execution_time_ms=3.0,
        sql="SELECT region, sales FROM accounts",
    )
    agent.schema_agent = StubSchema()
    agent.sql_agent = StubSQL(result)
    agent.viz_agent = StubViz()

    async def collect():
        return [e async for e in agent.run("sales by region")]

    events = asyncio.run(collect())
    result_event = next(e for e in events if e["type"] == "result")
    # Contract V2: queries mirrors top-level sql/row_count; provenance traces metrics
    assert result_event["queries"] == [
        {"sql": "SELECT region, sales FROM accounts", "row_count": 1}
    ]
    prov = result_event["provenance"]
    assert isinstance(prov, list) and prov
    cited = {(p["metric"], p["value"]) for p in prov}
    assert cited == {("sales", 120.0)}
    assert all(p["query_index"] == 0 for p in prov)


def test_cached_result_event_also_carries_queries_and_provenance():
    agent = _make_coordinator()
    cached = QueryResult(
        columns=["region", "sales"],
        rows=[{"region": "North", "sales": 70}],
        row_count=1,
        sql="SELECT region, sales FROM accounts",
        execution_time_ms=9.0,
    )
    agent.cache.put(cache_key(agent.connection_id, "sales by region"), cached)
    event = agent._cached_result_event("sales by region", cached)
    assert event["cached"] is True
    assert event["queries"] == [
        {"sql": "SELECT region, sales FROM accounts", "row_count": 1}
    ]
    assert event["provenance"] == [
        {"metric": "sales", "value": 70.0, "query_index": 0, "row_index": 0}
    ]


# ---------------------------------------------------------------------------
# Narrative grounding helpers
# ---------------------------------------------------------------------------

def test_extract_numbers_handles_commas_and_decimals():
    assert extract_numbers("returns rose to 2,810 (up 12.5%)") == [2810.0, 12.5]


def test_filter_key_points_drops_untraceable_numbers():
    traceable = traceable_values([Metric(label="return_count", value=679)])
    points = [
        "Returns totaled 2,810 units this period.",   # the old hallucination
        "Returns totaled 679 units.",                  # grounded
        "Sales grew through 2024.",                    # bare-year context allowed
        "Web channel outperformed store channel.",     # no numbers at all
    ]
    kept = filter_key_points_grounded(points, traceable)
    assert kept == [points[1], points[2], points[3]]


def test_metrics_to_text_tags_sources():
    metrics = [Metric(label="revenue", value=1234.5), Metric(label="cost", value=99.0)]
    text = metrics_to_text(metrics, metric_tags=["[q0.r2]", "[q1]"])
    assert "- revenue: 1,234.50 [q0.r2]" in text
    assert "- cost: 99.00 [q1]" in text


def test_traceable_values_includes_section_and_row_numbers():
    metrics = [Metric(label="m", value=10)]
    sections = [ReportSection(title="t", text="t", metrics=[Metric(label="s", value=20)])]
    rows = [{"a": 30, "d": "2024-01-01", "flag": True}]
    vals = traceable_values(metrics, sections, rows)
    assert vals == {10.0, 20.0, 30.0}
