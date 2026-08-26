"""Unit tests for the Wave-3 execute-inspect-refine loop (T1).

After execution and before synthesis, the result set is inspected for
quality problems; up to 2 refine iterations regenerate SQL with the
inspection report appended to the prompt, re-checking the cost gate each
time. The global budget of 4 executions per user query applies across all
retries including the Wave-1 broaden.
"""
import asyncio

from app.agents.coordinator import (
    CoordinatorAgent,
    ResultInspection,
    _result_score,
    inspect_result,
)
from app.agents.viz_agent import VizAgent
from app.engine.cache import QueryCache
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
    agent.connection_id = "refine-test"
    return agent


def _stub_schema() -> SchemaMap:
    return SchemaMap(
        tables=["accounts"],
        columns={"accounts": [
            ColumnInfo(column="region", type="text"),
            ColumnInfo(column="total", type="numeric"),
        ]},
    )


class ScriptedSQL:
    """generate_simple returns per-call SQLs; execute_query per-call rows."""

    def __init__(self, scripted_rows, sqls=None):
        self._scripted = list(scripted_rows)   # one entry per execution round
        self._sqls = list(sqls or [])
        self.calls = 0
        self.generations = 0
        self.feedbacks: list[str] = []

    async def estimate_cost(self, sql):
        return QueryCost(estimated_rows=10, estimated_cost=10, is_safe=True)

    async def generate_simple(self, question, schema, sample_text="", feedback=""):
        self.feedbacks.append(feedback or "")
        sql = self._sqls[min(self.generations, len(self._sqls) - 1)] if self._sqls \
            else "SELECT region FROM accounts"
        self.generations += 1
        return GeneratedSQL(sql=sql)

    async def execute_query(self, sql):
        rows = self._scripted[min(self.calls, len(self._scripted) - 1)]
        self.calls += 1
        cols = list(rows[0].keys()) if rows else ["region"]
        return QueryResult(columns=cols, rows=rows, row_count=len(rows), sql=sql)


def _run(agent, question):
    async def collect():
        return [e async for e in agent.run(question)]
    return asyncio.run(collect())


# ---------------------------------------------------------------------------
# inspect_result — signal detection
# ---------------------------------------------------------------------------

def test_inspect_flags_zero_rows():
    result = QueryResult(columns=["region"], rows=[], row_count=0, sql="SELECT 1")
    inspection = inspect_result("totals", "SELECT 1", result)
    assert inspection.has_issues
    assert [i.code for i in inspection.issues] == ["empty"]
    assert "ZERO rows" in inspection.feedback()


def test_inspect_flags_degenerate_single_row_aggregate_for_breakdown_question():
    question = "how many churned accounts by plan tier"
    sql = "SELECT COUNT(*) AS churned FROM accounts"
    result = QueryResult(
        columns=["churned"], rows=[{"churned": 110}], row_count=1, sql=sql,
    )
    inspection = inspect_result(question, sql, result)
    assert [i.code for i in inspection.issues] == ["degenerate_aggregate"]
    assert "GROUP BY" in inspection.feedback()


def test_inspect_accepts_single_row_when_question_is_kpi():
    question = "how many churned accounts are there"
    sql = "SELECT COUNT(*) AS churned FROM accounts"
    result = QueryResult(
        columns=["churned"], rows=[{"churned": 110}], row_count=1, sql=sql,
    )
    assert not inspect_result(question, sql, result).has_issues


def test_inspect_flags_null_dominant_column():
    sql = "SELECT region, total FROM accounts GROUP BY region"
    rows = [
        {"region": f"r{i}", "total": None} for i in range(5)
    ] + [{"region": "ok", "total": 7}]
    # 5 of 6 rows NULL → >80% null in 'total'
    result = QueryResult(columns=["region", "total"], rows=rows,
                         row_count=len(rows), sql=sql)
    codes = [i.code for i in inspect_result("breakdown by region", sql, result).issues]
    assert "null_dominant" in codes


def test_inspect_flags_uniform_numeric_values():
    sql = "SELECT region, total FROM accounts GROUP BY region"
    rows = [{"region": f"r{i}", "total": 42} for i in range(4)]
    result = QueryResult(columns=["region", "total"], rows=rows,
                         row_count=4, sql=sql)
    codes = [i.code for i in inspect_result("breakdown by region", sql, result).issues]
    assert "uniform_values" in codes


def test_inspect_clean_on_healthy_breakdown():
    sql = "SELECT region, SUM(total) AS n FROM accounts GROUP BY region"
    rows = [{"region": "a", "n": 3}, {"region": "b", "n": 9}, {"region": "c", "n": 1}]
    result = QueryResult(columns=["region", "n"], rows=rows, row_count=3, sql=sql)
    inspection = inspect_result("sales by region", sql, result)
    assert isinstance(inspection, ResultInspection)
    assert not inspection.has_issues


def test_result_score_prefers_non_empty_then_richer_then_earlier():
    empty = QueryResult(columns=["a"], rows=[], row_count=0)
    thin = QueryResult(columns=["a"], rows=[{"a": 1}], row_count=1)
    rich = QueryResult(
        columns=["a", "b"], rows=[{"a": 1, "b": 2}, {"a": 3, "b": 4}], row_count=2,
    )
    assert _result_score(empty) < _result_score(thin) < _result_score(rich)
    # ties prefer earlier — strict-greater comparison keeps the incumbent
    thin2 = QueryResult(columns=["a"], rows=[{"a": 9}], row_count=1)
    assert not (_result_score(thin2) > _result_score(thin))


# ---------------------------------------------------------------------------
# Refine loop end-to-end on the simple path
# ---------------------------------------------------------------------------

def test_refine_converges_bad_then_good():
    agent = _make_coordinator()

    class StubSchema:
        async def fetch_schema(self):
            return _stub_schema()

    bad_sql = "SELECT COUNT(*) AS n FROM accounts"
    good_rows = [{"region": "east", "total": 5}, {"region": "west", "total": 2}]
    good_sql = "SELECT region, SUM(total) AS total FROM accounts GROUP BY region"
    sql_agent = ScriptedSQL(
        scripted_rows=[[{"n": 110}], good_rows],
        sqls=[bad_sql, good_sql],
    )
    agent.schema_agent = StubSchema()
    agent.sql_agent = sql_agent

    events = _run(agent, "show me totals by region")

    assert not any(e["type"] == "error" for e in events), events
    refine_events = [e for e in events if e.get("stage") == "refine"]
    assert len(refine_events) == 1  # one refinement sufficed
    assert "attempt 1 of 2" in refine_events[0]["message"]
    # The inspection report reached the generator as feedback
    assert any("single overall-aggregate row" in f for f in sql_agent.feedbacks)
    result_event = next(e for e in events if e["type"] == "result")
    assert result_event["row_count"] == 2
    assert sql_agent.calls == 2  # initial + one refine


def test_refine_budget_caps_total_executions():
    agent = _make_coordinator()

    class StubSchema:
        async def fetch_schema(self):
            return _stub_schema()

    # Every round degenerates the same way (overall aggregate for a
    # breakdown question) → refines never improve → loop must stop at the
    # refine cap (initial + 2 refines = 3 executions).
    sql_agent = ScriptedSQL(
        scripted_rows=[[{"n": 1}]] * 3,
        sqls=["SELECT COUNT(*) AS n FROM accounts"],
    )
    agent.schema_agent = StubSchema()
    agent.sql_agent = sql_agent

    events = _run(agent, "totals by region")
    assert sql_agent.calls == 3
    assert any(e["type"] == "result" for e in events)


def test_zero_row_after_broaden_flows_into_refine_and_hits_execution_cap():
    agent = _make_coordinator()

    class StubSchema:
        async def fetch_schema(self):
            return _stub_schema()

    # exec1 zero → broaden exec2 zero → refine exec3 zero → refine exec4 zero
    # → budget exhausted → actionable error, never a fifth execution.
    sql_agent = ScriptedSQL(scripted_rows=[[], [], [], []])
    agent.schema_agent = StubSchema()
    agent.sql_agent = sql_agent

    events = _run(agent, "how many accounts are there")
    assert sql_agent.calls == 4  # hard budget across broaden + refines
    errors = [e for e in events if e["type"] == "error"]
    assert len(errors) == 1
    assert "zero rows" in errors[0]["message"]
    refine_events = [e for e in events if e.get("stage") == "refine"]
    assert len(refine_events) == 2


def test_refine_keeps_better_result_and_drops_worse():
    agent = _make_coordinator()

    class StubSchema:
        async def fetch_schema(self):
            return _stub_schema()

    # First attempt trips the uniform-value signal (all totals are 5); the
    # refinement comes back THINNER (fewer filled cells) → the richer
    # original must be kept.
    sql_agent = ScriptedSQL(
        scripted_rows=[
            [
                {"region": "a", "total": 5},
                {"region": "b", "total": 5},
                {"region": "c", "total": 5},
            ],  # uniform → flagged
            [{"region": "c", "total": 1}],  # thinner refinement → rejected
        ],
    )
    agent.schema_agent = StubSchema()
    agent.sql_agent = sql_agent

    events = _run(agent, "totals by region")
    assert any(e.get("stage") == "refine" for e in events)
    result_event = next(e for e in events if e["type"] == "result")
    # The richer (first, uniform-but-3-row) set beat the thinner refinement
    assert result_event["row_count"] == 3


def test_refine_skipped_when_cost_gate_rejects_refinement():
    agent = _make_coordinator()

    class StubSchema:
        async def fetch_schema(self):
            return _stub_schema()

    sql_agent = ScriptedSQL(scripted_rows=[[{"n": 1}]] * 2)

    estimates = iter([
        QueryCost(estimated_rows=10, estimated_cost=10, is_safe=True),
        QueryCost(estimated_rows=10, estimated_cost=999_999, is_safe=False,
                  reason="estimated cost 999,999 exceeds budget"),
    ])

    async def estimate_cost(sql):
        return next(estimates)

    sql_agent.estimate_cost = estimate_cost
    agent.schema_agent = StubSchema()
    agent.sql_agent = sql_agent

    events = _run(agent, "totals by region")
    # Refinement was cost-blocked → keep the original result, no crash
    assert sql_agent.calls == 1
    assert not any(e["type"] == "error" for e in events)
    assert any(e["type"] == "result" for e in events)
