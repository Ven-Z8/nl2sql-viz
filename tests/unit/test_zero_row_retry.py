"""Unit tests for planner retry-on-empty (T2) and clarify-on-ambiguity.

The broadened retry relaxes non-essential filters ONCE when planned queries
all return zero rows; ambiguity about the focus table emits a clarify round
(via the injected ask_user callback) instead of guessing.
"""
import asyncio
import logging

from app.agents.coordinator import (
    CoordinatorAgent,
    ambiguous_focus_tables,
    detect_relaxable_filters,
)
from app.agents.viz_agent import VizAgent
from app.engine.cache import QueryCache
from app.models import (
    ColumnInfo,
    GeneratedSQL,
    QueryCost,
    QueryResult,
    SchemaMap,
    SubQuery,
)


class ScriptedSQL:
    """plan_analysis → fixed sub-queries; execute_query → scripted rounds."""

    def __init__(self, scripted_rows, sql="SELECT total FROM accounts", plan=None):
        self._scripted = list(scripted_rows)  # one entry per execution round
        self._sql = sql
        self._plan = plan or []
        self.calls = 0
        self.feedbacks: list[str] = []

    async def estimate_cost(self, sql):
        return QueryCost(estimated_rows=10, estimated_cost=10, is_safe=True)

    async def plan_analysis(self, question, schema, sample_text=""):
        return list(self._plan)

    async def generate_simple(self, question, schema, sample_text="", feedback=""):
        self.feedbacks.append(feedback or "")
        return GeneratedSQL(sql=self._sql)

    async def execute_query(self, sql):
        rows = self._scripted[min(self.calls, len(self._scripted) - 1)]
        self.calls += 1
        cols = list(rows[0].keys()) if rows else ["total"]
        return QueryResult(columns=cols, rows=rows, row_count=len(rows), sql=sql)


def _make_coordinator() -> CoordinatorAgent:
    agent = CoordinatorAgent()
    agent.viz_agent = VizAgent()
    agent.cache = QueryCache()
    agent.connection_id = "retry-test"
    return agent


def _stub_schema(tables=("accounts",)) -> SchemaMap:
    return SchemaMap(
        tables=list(tables),
        columns={
            t: [ColumnInfo(column="total", type="numeric"),
                ColumnInfo(column="region", type="text")]
            for t in tables
        },
    )


def _run(agent, question, **kwargs):
    async def collect():
        return [e async for e in agent.run(question, **kwargs)]
    return asyncio.run(collect())


# ---------------------------------------------------------------------------
# detect_relaxable_filters / ambiguous_focus_tables — pure helpers
# ---------------------------------------------------------------------------

def test_detect_relaxable_filters_finds_having_and_dates():
    sql = ("SELECT region FROM accounts "
           "WHERE order_date BETWEEN '2020-01-01' AND '2020-12-31' "
           "HAVING SUM(total) > 100")
    assert set(detect_relaxable_filters(sql)) == {"HAVING threshold", "date-range bounds"}


def test_detect_relaxable_filters_empty_for_plain_sql():
    assert detect_relaxable_filters("SELECT region FROM accounts") == []


def test_ambiguous_focus_tables_dedups_and_caps():
    tables = ["orders", "customers", "orders", "items", "extra", "more"]
    assert ambiguous_focus_tables(tables) == ["orders", "customers", "items", "extra"]
    assert ambiguous_focus_tables([]) == []
    assert ambiguous_focus_tables(["only_one"]) == ["only_one"]


# ---------------------------------------------------------------------------
# Complex path: all sub-queries zero rows → ONE broadened retry round
# ---------------------------------------------------------------------------

def test_complex_zero_rows_triggers_single_broadened_retry(caplog):
    agent = _make_coordinator()

    class StubSchema:
        async def fetch_schema(self):
            return _stub_schema()

    sql_agent = ScriptedSQL(
        # round 1: two parallel executions, both zero; broadened round: rows
        scripted_rows=[[], [], [{"total": 500}]],
        plan=[
            SubQuery(id="q1", question="revenue by region", purpose="revenue"),
            SubQuery(id="q2", question="cost by region", purpose="cost"),
        ],
    )
    agent.schema_agent = StubSchema()
    agent.sql_agent = sql_agent

    with caplog.at_level(logging.INFO, logger="app.agents.coordinator"):
        events = _run(agent, "compare revenue versus cost by region")

    # No error event — the broadened retry recovered
    assert not any(e["type"] == "error" for e in events), events
    result_event = next(e for e in events if e["type"] == "result")
    # Both sub-queries succeeded on the broadened round → two shipped results
    assert len(result_event["queries"]) == 2
    assert result_event["queries"][0]["row_count"] == 1
    # Exactly ONE regeneration round used the broaden feedback (once per query)
    broaden_calls = [f for f in sql_agent.feedbacks if "GROUP BY shape" in f]
    assert len(broaden_calls) == 2
    # Which filters were relaxed is logged
    assert any("[ZERO-ROW][RELAX]" in r.getMessage() for r in caplog.records)


def test_complex_retry_also_zero_rows_emits_error():
    agent = _make_coordinator()

    class StubSchema:
        async def fetch_schema(self):
            return _stub_schema()

    sql_agent = ScriptedSQL(
        scripted_rows=[[]],  # every execution returns zero rows
        plan=[SubQuery(id="q1", question="revenue", purpose="revenue")],
    )
    agent.schema_agent = StubSchema()
    agent.sql_agent = sql_agent

    events = _run(agent, "compare revenue versus cost")
    errors = [e for e in events if e["type"] == "error"]
    assert len(errors) == 1
    assert "zero rows" in errors[0]["message"]
    assert not any(e["type"] == "result" for e in events)


# ---------------------------------------------------------------------------
# Simple path: single query zero rows → ONE broadened regen retry
# ---------------------------------------------------------------------------

def test_simple_path_broadened_retry_recovers(caplog):
    agent = _make_coordinator()
    question = "how many accounts total"

    class StubSchema:
        async def fetch_schema(self):
            return _stub_schema()

    # First attempt over-filters via an impossible HAVING threshold (zero
    # rows); the broadened retry drops it and returns data. Only declared
    # columns are referenced so the schema validator accepts the SQL.
    sql_agent = ScriptedSQL(
        scripted_rows=[[], [{"region": "North"}]],
        sql="SELECT region FROM accounts HAVING SUM(total) > 100000",
    )
    agent.schema_agent = StubSchema()
    agent.sql_agent = sql_agent

    with caplog.at_level(logging.INFO, logger="app.agents.coordinator"):
        events = _run(agent, question)

    assert not any(e["type"] == "error" for e in events)
    result_event = next(e for e in events if e["type"] == "result")
    assert result_event["row_count"] == 1
    assert "[ZERO-ROW]" in caplog.text
    assert "[ZERO-ROW][RELAX]" in caplog.text  # date-range bounds named
    assert any("GROUP BY shape" in f for f in sql_agent.feedbacks)


# ---------------------------------------------------------------------------
# Clarify: ambiguity about focus table asks instead of guessing
# ---------------------------------------------------------------------------

def _ambiguous_setup(scripted_rounds):
    """Complex-routed question naming TWO tables; scripted execution rounds."""
    agent = _make_coordinator()

    class StubSchema:
        async def fetch_schema(self):
            return _stub_schema(("orders", "customers"))

    sql_agent = ScriptedSQL(
        scripted_rows=scripted_rounds,
        sql="SELECT total FROM orders",
        plan=[SubQuery(id="q1", question="totals by table", purpose="totals")],
    )
    agent.schema_agent = StubSchema()
    agent.sql_agent = sql_agent
    return agent, sql_agent


def test_clarify_emitted_on_ambiguity_and_choice_is_used():
    agent, sql_agent = _ambiguous_setup([[], [{"total": 300}]])
    asked: list[tuple[str, list[str]]] = []

    async def ask_user(question, options):
        asked.append((question, options))
        return 1  # choose "customers"

    events = _run(agent, "compare orders versus customers totals", ask_user=ask_user)

    # Exactly one clarify round was offered to the transport layer
    assert len(asked) == 1
    question_text, options = asked[0]
    assert options == ["orders", "customers"]
    assert isinstance(question_text, str) and question_text
    assert not any(e["type"] == "error" for e in events)
    assert any(e["type"] == "result" for e in events)
    # Regeneration happened AFTER clarify, with a focus-table feedback
    assert any("customers" in f for f in sql_agent.feedbacks if f)


def test_clarify_timeout_proceeds_with_broadened_retry():
    agent, sql_agent = _ambiguous_setup([[], [{"total": 300}]])

    async def ask_user(question, options):
        return None  # transport-level 120s timeout / refusal

    events = _run(agent, "compare orders versus customers totals", ask_user=ask_user)

    assert not any(e["type"] == "error" for e in events)
    assert any(e["type"] == "result" for e in events)
    # Fell through to the broadened retry rather than re-asking
    assert any("GROUP BY shape" in f for f in sql_agent.feedbacks)


def test_no_clarify_when_focus_table_is_unambiguous():
    agent = _make_coordinator()

    class StubSchema:
        async def fetch_schema(self):
            return _stub_schema(("orders", "customers"))

    # Only "orders" is named by the question → single candidate → no clarify,
    # even though the first round returns zero rows.
    sql_agent = ScriptedSQL(scripted_rows=[[], [{"total": 300}]],
                            sql="SELECT total FROM orders")
    agent.schema_agent = StubSchema()
    agent.sql_agent = sql_agent
    questions_asked: list[str] = []

    async def ask_user(question, options):
        questions_asked.append(question)
        return None

    events = _run(agent, "how many orders are there", ask_user=ask_user)
    assert questions_asked == []
    assert not any(e["type"] == "error" for e in events)
    assert any(e["type"] == "result" for e in events)
