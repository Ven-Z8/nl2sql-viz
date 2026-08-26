"""Unit tests for Wave-3 cost-block auto-tightening (T2).

When the cost gate rejects a query for exceeding MAX_COST, the pipeline
deterministically tightens the SQL — LIMIT cap, then date-range narrowing /
planner-marked optional-join drop — before failing with an actionable error
that reports the original estimate vs the budget.
"""
import asyncio

from app.agents.coordinator import (
    CoordinatorAgent,
    drop_optional_join,
    tighten_date_range,
    tighten_limit_cap,
    tighten_sql,
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

BUDGET = 100_000.0


def _make_coordinator() -> CoordinatorAgent:
    agent = CoordinatorAgent()
    agent.viz_agent = VizAgent()
    agent.cache = QueryCache()
    agent.connection_id = "tighten-test"
    return agent


def _stub_schema() -> SchemaMap:
    return SchemaMap(
        tables=["accounts"],
        columns={"accounts": [
            ColumnInfo(column="region", type="text"),
            ColumnInfo(column="total", type="numeric"),
            ColumnInfo(column="created", type="date"),
        ]},
    )


ANALYTICAL_SQL = (
    "SELECT region, SUM(total) AS n FROM accounts "
    "WHERE created BETWEEN '2020-01-01' AND '2024-12-31' GROUP BY region"
)


# ---------------------------------------------------------------------------
# Tighten strategies — pure helpers
# ---------------------------------------------------------------------------

def test_tighten_limit_cap_adds_limit_proportional_to_budget():
    tightened, how = tighten_limit_cap(ANALYTICAL_SQL, BUDGET)
    assert "LIMIT 1000" in tightened          # budget // 100
    assert "LIMIT" in how
    # GROUP BY / WHERE shape preserved
    assert "GROUP BY region" in tightened and "SUM(total)" in tightened


def test_tighten_limit_cap_halves_existing_limit():
    sql = ANALYTICAL_SQL + " LIMIT 50000"
    tightened, _how = tighten_limit_cap(sql, BUDGET)
    assert "LIMIT 25000" in tightened


def test_tighten_limit_cap_respects_floor_and_handles_cte():
    tightened, _ = tighten_limit_cap("WITH x AS (SELECT 1 AS a) SELECT a FROM x", 10.0)
    assert "LIMIT 200" in tightened           # _LIMIT_CAP_MIN floor


def test_tighten_date_range_narrows_between_to_recent_half():
    tightened, how = tighten_date_range(ANALYTICAL_SQL)
    # midpoint of 2020-01-01..2024-12-31 → start moves to 2022-07-02
    assert "'2022-07-02'" in tightened and "'2024-12-31'" in tightened
    assert "date window" in how


def test_tighten_date_range_noop_without_dates():
    assert tighten_date_range("SELECT region FROM accounts") is None


def test_drop_optional_join_requires_explicit_marker():
    marked = ("SELECT a.region FROM accounts a "
              "LEFT JOIN regions r /* optional_join */ ON a.region = r.name")
    dropped, how = drop_optional_join(marked)
    assert "JOIN" not in dropped.upper()
    assert "optional join" in how
    # Unmarked joins are load-bearing — never touched
    unmarked = ("SELECT a.region FROM accounts a "
                "LEFT JOIN regions r ON a.region = r.name")
    assert drop_optional_join(unmarked) is None


def test_tighten_sql_dispatch_by_attempt():
    assert tighten_sql(ANALYTICAL_SQL, 1, BUDGET) is not None       # limit
    assert tighten_sql(ANALYTICAL_SQL, 2, BUDGET) is not None       # dates
    assert tighten_sql("SELECT region FROM accounts", 2, BUDGET) is None
    assert tighten_sql(ANALYTICAL_SQL, 3, BUDGET) is None           # no attempt 3


# ---------------------------------------------------------------------------
# Pipeline behavior: reject → tighten → pass; reject ×3 → actionable error
# ---------------------------------------------------------------------------

class CostScriptedSQL:
    """estimate_cost replays a queue of estimated costs (last one sticks)."""

    def __init__(self, estimates, result_rows):
        self._estimates = list(estimates)   # one per gate check
        self._gate_idx = -1
        self._result_rows = result_rows
        self.executed_sqls: list[str] = []
        self.calls = 0

    async def estimate_cost(self, sql):
        self._gate_idx += 1
        cost = self._estimates[min(self._gate_idx, len(self._estimates) - 1)]
        return QueryCost(
            estimated_rows=max(cost, 10),
            estimated_cost=cost,
            is_safe=cost <= BUDGET,
            reason="" if cost <= BUDGET else f"estimated cost {cost:,.0f} too high",
        )

    async def generate_simple(self, question, schema, sample_text="", feedback=""):
        return GeneratedSQL(sql=ANALYTICAL_SQL)

    async def execute_query(self, sql):
        self.calls += 1
        self.executed_sqls.append(sql)
        rows = self._result_rows
        cols = list(rows[0].keys()) if rows else ["region"]
        return QueryResult(columns=cols, rows=rows, row_count=len(rows), sql=sql)


def _run(agent, question):
    async def collect():
        return [e async for e in agent.run(question)]
    return asyncio.run(collect())


def test_cost_reject_then_tighten_then_execute(monkeypatch):
    import app.agents.coordinator as coord

    monkeypatch.setattr(coord, "MAX_COST", BUDGET)
    agent = _make_coordinator()

    class StubSchema:
        async def fetch_schema(self):
            return _stub_schema()

    # Gate checks: initial 187613 (rejected) → after LIMIT-tighten 118652
    # still rejected? No — second estimate passes to prove recovery.
    rows = [{"region": "east", "n": 5}]
    sql_agent = CostScriptedSQL([187_613, 90_000], rows)
    agent.schema_agent = StubSchema()
    agent.sql_agent = sql_agent

    events = _run(agent, "healthcare cost by region")

    tightening = [e for e in events if e.get("stage") == "cost" and "Tightening" in e["message"]]
    assert len(tightening) == 1
    assert "attempt 1" in tightening[0]["message"]
    # The executed SQL carries the automatic LIMIT cap
    assert any("LIMIT" in s.upper() for s in sql_agent.executed_sqls)
    assert not any(e["type"] == "error" for e in events)
    assert any(e["type"] == "result" for e in events)


def test_cost_reject_three_times_yields_actionable_error(monkeypatch):
    import app.agents.coordinator as coord

    monkeypatch.setattr(coord, "MAX_COST", BUDGET)
    agent = _make_coordinator()

    class StubSchema:
        async def fetch_schema(self):
            return _stub_schema()

    # All three gate checks reject: 187613 → 118652 → 118653.
    sql_agent = CostScriptedSQL([187_613, 118_652, 118_653], [])
    agent.schema_agent = StubSchema()
    agent.sql_agent = sql_agent

    events = _run(agent, "healthcare analytical question")

    errors = [e for e in events if e["type"] == "error"]
    assert len(errors) == 1
    message = errors[0]["message"]
    # Actionable: original estimate vs budget, both numbers present
    assert "187,613" in message
    assert "100,000" in message
    assert "Tightening" in message or "tightening" in message
    assert not any(e["type"] == "result" for e in events)
    assert sql_agent.calls == 0  # never executed


def test_explain_failure_keeps_legacy_guided_retry(monkeypatch):
    import app.agents.coordinator as coord

    monkeypatch.setattr(coord, "MAX_COST", BUDGET)
    agent = _make_coordinator()

    class StubSchema:
        async def fetch_schema(self):
            return _stub_schema()

    class ExplainBrokenSQL(CostScriptedSQL):
        async def estimate_cost(self, sql):
            raise RuntimeError("EXPLAIN unavailable")

    sql_agent = ExplainBrokenSQL([], [])
    gen_count = {"n": 0}

    async def generate_simple(question, schema, sample_text="", feedback=""):
        gen_count["n"] += 1
        return GeneratedSQL(sql=ANALYTICAL_SQL)

    sql_agent.generate_simple = generate_simple
    agent.schema_agent = StubSchema()
    agent.sql_agent = sql_agent

    events = _run(agent, "totals by region")
    errors = [e for e in events if e["type"] == "error"]
    assert len(errors) == 1
    assert "blocked by cost limit" in errors[0]["message"]
    # Legacy path: exactly one guided regeneration attempt was made
    assert gen_count["n"] == 2
