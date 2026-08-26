"""Unit tests for the Wave-3 grouped-result answer presentation fix (T3).

The simple path used to slam the KPI template onto GROUP BY results — a
3-row plan_tier breakdown rendered as "Total Churned Accounts 110 | Latest
Churned Accounts 34". Grouped/multi-row results now enumerate their top
segments with actual shipped values, each number traced to its row.
"""
import asyncio

from app.agents.coordinator import CoordinatorAgent, _is_grouped_result
from app.agents.viz_agent import VizAgent
from app.engine.cache import QueryCache, cache_key
from app.models import (
    ColumnInfo,
    GeneratedSQL,
    QueryCost,
    QueryResult,
    SchemaMap,
)


def _make_coordinator() -> CoordinatorAgent:
    agent = CoordinatorAgent()
    agent.viz_agent = VizAgent()
    agent.cache = QueryCache()
    agent.connection_id = "grouped-test"
    return agent


def _stub_schema() -> SchemaMap:
    return SchemaMap(
        tables=["accounts"],
        columns={"accounts": [
            ColumnInfo(column="plan_tier", type="text"),
            ColumnInfo(column="churned", type="int"),
        ]},
    )


CHURN_SQL = (
    "SELECT plan_tier, COUNT(*) AS churned FROM accounts GROUP BY plan_tier"
)


def _churn_result() -> QueryResult:
    rows = [
        {"plan_tier": "Enterprise", "churned": 34},
        {"plan_tier": "Basic", "churned": 37},
        {"plan_tier": "Pro", "churned": 39},
    ]
    return QueryResult(columns=["plan_tier", "churned"], rows=rows,
                       row_count=3, sql=CHURN_SQL)


class StubSQL:
    def __init__(self, result: QueryResult) -> None:
        self.result = result

    async def estimate_cost(self, sql):
        return QueryCost(estimated_rows=10, estimated_cost=10, is_safe=True)

    async def generate_simple(self, question, schema, sample_text="", feedback=""):
        return GeneratedSQL(sql=self.result.sql)

    async def execute_query(self, sql):
        return self.result


def _run(agent, question):
    async def collect():
        return [e async for e in agent.run(question)]
    return asyncio.run(collect())


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def test_grouped_detection_via_group_by_and_categorical_column():
    assert _is_grouped_result(CHURN_SQL, _churn_result())
    no_group_by_sql = "SELECT plan_tier, churned FROM accounts"
    # rows>1 + categorical first column with distinct values → still grouped
    assert _is_grouped_result(no_group_by_sql, _churn_result())
    single = QueryResult(columns=["plan_tier", "churned"],
                         rows=[{"plan_tier": "Pro", "churned": 39}],
                         row_count=1, sql=CHURN_SQL)
    assert not _is_grouped_result(CHURN_SQL, single)
    empty = QueryResult(columns=[], rows=[], row_count=0, sql=CHURN_SQL)
    assert not _is_grouped_result(CHURN_SQL, empty)


# ---------------------------------------------------------------------------
# Presentation: enumerate top segments instead of Total/Latest slam
# ---------------------------------------------------------------------------

def test_grouped_answer_enumerates_segments_desc():
    agent = _make_coordinator()
    grouped = agent.grounded_grouped_answer([_churn_result()])
    assert grouped is not None
    metrics, traces, text = grouped
    # Regression guard: the old misleading KPI-slam must be gone
    assert "Total" not in text and "Latest" not in text
    assert text == "Churned by Plan Tier: Pro 39, Basic 37, Enterprise 34"
    assert [(m.label, m.value) for m in metrics] == [
        ("Pro", 39.0), ("Basic", 37.0), ("Enterprise", 34.0),
    ]


def test_grouped_provenance_maps_row_index_to_original_position():
    from app.models import GroundedAnswer

    agent = _make_coordinator()
    metrics, traces, _text = agent.grounded_grouped_answer([_churn_result()])
    # Rows ship in original order; Pro sits at ORIGINAL index 2 even though
    # it is presented first (highest value).
    assert [(t.query_index, t.row_index, t.column) for t in traces] == [
        (0, 2, "churned"), (0, 1, "churned"), (0, 0, "churned"),
    ]
    answer = GroundedAnswer(text="x", metrics=metrics)
    prov = agent.provenance_for_answer(answer, traces, [_churn_result()])
    by_metric = {p["metric"]: p for p in prov}
    assert by_metric["Pro"] == {
        "metric": "Pro", "value": 39.0, "query_index": 0, "row_index": 2,
    }
    assert by_metric["Enterprise"]["row_index"] == 0


def test_grouped_enumeration_caps_at_five_segments():
    rows = [{"tier": f"t{i}", "n": i} for i in range(9)]
    result = QueryResult(columns=["tier", "n"], rows=rows, row_count=9,
                         sql="SELECT tier, COUNT(*) AS n FROM x GROUP BY tier")
    agent = _make_coordinator()
    _metrics, _traces, text = agent.grounded_grouped_answer([result])
    assert text.count(",") == 4          # five segments max
    assert "t8 8" in text                # top value first


def test_kpi_template_untouched_for_single_scalar():
    agent = _make_coordinator()

    class StubSchema:
        async def fetch_schema(self):
            return _stub_schema()

    result = QueryResult(columns=["churned"], rows=[{"churned": 42}],
                         row_count=1, sql="SELECT COUNT(*) AS churned FROM accounts")
    agent.schema_agent = StubSchema()
    agent.sql_agent = StubSQL(result)

    events = _run(agent, "how many churned accounts are there")
    result_event = next(e for e in events if e["type"] == "result")
    assert result_event["answer"]["text"] == "Churned: 42"


# ---------------------------------------------------------------------------
# End-to-end: live repro shape flows through run() and cache hits alike
# ---------------------------------------------------------------------------

def test_plan_tier_breakdown_repro_enumerates_instead_of_total_latest():
    agent = _make_coordinator()

    class StubSchema:
        async def fetch_schema(self):
            return _stub_schema()

    agent.schema_agent = StubSchema()
    agent.sql_agent = StubSQL(_churn_result())

    events = _run(agent, "how many churned accounts by plan tier")
    result_event = next(e for e in events if e["type"] == "result")
    answer = result_event["answer"]
    assert answer["text"].startswith("Churned by Plan Tier:")
    assert "Total Churned Accounts" not in answer["text"]
    # Every cited number is traceable via provenance into queries[0]
    prov = result_event["provenance"]
    cited_values = {(p["metric"], p["value"]) for p in prov}
    assert ("Pro", 39.0) in cited_values
    assert all(p["query_index"] == 0 for p in prov)


def test_cached_grouped_event_matches_fresh_presentation():
    agent = _make_coordinator()
    cached = _churn_result()
    agent.cache.put(cache_key(agent.connection_id, "how many churned accounts by plan tier"), cached)
    event = agent._cached_result_event("how many churned accounts by plan tier", cached)
    assert event["answer"]["text"] == \
        "Churned by Plan Tier: Pro 39, Basic 37, Enterprise 34"
    assert any(p["metric"] == "Basic" and p["row_index"] == 1
               for p in event["provenance"])
