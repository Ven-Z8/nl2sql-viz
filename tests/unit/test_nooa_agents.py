"""Tests for NOOA agent instantiation and deterministic helpers.

These tests verify that:
1. All NOOA agents can be instantiated
2. Deterministic helper methods work correctly
3. Pydantic models validate properly
4. SQL guard rejects unsafe queries
5. Cache and result management work
"""

import asyncio

import pytest
from unittest.mock import MagicMock

from app.models import (
    ChartPlan,
    ChartType,
    ColumnInfo,
    DataStrategy,
    GeneratedSQL,
    QueryResult,
    SchemaMap,
)
from app.db.guard import validate_read_only
from app.engine.cache import QueryCache, cache_key
from app.engine.results import classify_size, prepare_for_viz, stratified_sample
from app.agents.schema_agent import SchemaAgent
from app.agents.sql_agent import SQLAgent
from app.agents.viz_agent import VizAgent
from app.agents.coordinator import CoordinatorAgent


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class TestModels:
    def test_schema_map_compact_repr(self):
        schema = SchemaMap(
            tables=["users", "orders"],
            columns={
                "users": [
                    ColumnInfo(column="id", type="integer", constraint="PRIMARY KEY"),
                    ColumnInfo(column="name", type="text"),
                ],
                "orders": [
                    ColumnInfo(column="id", type="integer", constraint="PRIMARY KEY"),
                    ColumnInfo(column="user_id", type="integer", foreign_table="users", foreign_column="id"),
                ],
            },
            row_estimates={"users": 500, "orders": 5000},
        )
        text = schema.compact_repr()
        assert "users(~500 rows)" in text
        assert "orders(~5,000 rows)" in text
        assert "FK→users.id" in text
        assert "[PK]" in text

    def test_query_result_sample(self):
        rows = [{"id": i, "val": i * 10} for i in range(100)]
        result = QueryResult(columns=["id", "val"], rows=rows, row_count=100)
        sample = result.sample(5)
        assert len(sample) == 10  # head 5 + tail 5

    def test_chart_plan_enum(self):
        plan = ChartPlan(chart_type=ChartType.LINE, data_strategy=DataStrategy.INLINE, title="Revenue")
        assert plan.chart_type == ChartType.LINE
        assert plan.data_strategy == DataStrategy.INLINE


# ---------------------------------------------------------------------------
# SQL Guard tests
# ---------------------------------------------------------------------------

class TestSQLGuard:
    def test_select_passes(self):
        validate_read_only("SELECT count(*) FROM users")

    def test_with_passes(self):
        validate_read_only("WITH cte AS (SELECT 1) SELECT * FROM cte")

    def test_insert_rejected(self):
        with pytest.raises(ValueError, match="read-only"):
            validate_read_only("INSERT INTO users VALUES (1)")

    def test_drop_rejected(self):
        with pytest.raises(ValueError, match="read-only"):
            validate_read_only("DROP TABLE users")

    def test_multiple_statements_rejected(self):
        with pytest.raises(ValueError, match="single statement"):
            validate_read_only("SELECT 1; SELECT 2")

    def test_empty_rejected(self):
        with pytest.raises(ValueError, match="empty"):
            validate_read_only("")


# ---------------------------------------------------------------------------
# Cache tests
# ---------------------------------------------------------------------------

class TestCache:
    def test_put_and_get(self):
        cache = QueryCache()
        key = cache_key("conn1", "SELECT 1")
        result = QueryResult(columns=["a"], rows=[{"a": 1}], row_count=1)
        cache.put(key, result)
        assert cache.get(key) is not None
        assert cache.get(key).row_count == 1

    def test_miss_returns_none(self):
        cache = QueryCache()
        assert cache.get("nonexistent") is None

    def test_invalidate_prefix(self):
        cache = QueryCache()
        cache.put("q:conn1:abc", QueryResult(columns=[], rows=[], row_count=0))
        cache.put("q:conn1:def", QueryResult(columns=[], rows=[], row_count=0))
        cache.put("q:conn2:ghi", QueryResult(columns=[], rows=[], row_count=0))
        removed = cache.invalidate_prefix("q:conn1:")
        assert removed == 2
        assert cache.get("q:conn2:ghi") is not None

    def test_stats(self):
        cache = QueryCache()
        cache.get("miss")
        assert cache.stats["misses"] == 1

    def test_cache_key_normalization(self):
        k1 = cache_key("c1", "SELECT   count(*) FROM  users")
        k2 = cache_key("c1", "select count(*) from users")
        assert k1 == k2  # normalized to same key


# ---------------------------------------------------------------------------
# Result management tests
# ---------------------------------------------------------------------------

class TestResults:
    def test_inline_for_small(self):
        result = QueryResult(columns=["a"], rows=[{"a": 1}] * 500, row_count=500)
        assert classify_size(result) == DataStrategy.INLINE

    def test_sampled_for_medium(self):
        result = QueryResult(columns=["a"], rows=[{"a": 1}] * 5000, row_count=5000)
        assert classify_size(result) == DataStrategy.SAMPLED

    def test_aggregated_for_large(self):
        result = QueryResult(columns=["a"], rows=[{"a": 1}] * 200_000, row_count=200_000)
        assert classify_size(result) == DataStrategy.AGGREGATED

    def test_stratified_sample_preserves_size(self):
        rows = [{"id": i, "val": i} for i in range(10_000)]
        sampled = stratified_sample(rows, 1000)
        assert len(sampled) == 1000

    def test_prepare_for_viz_inline(self):
        result = QueryResult(columns=["x"], rows=[{"x": 1}, {"x": 2}], row_count=2)
        strategy, data, meta = prepare_for_viz(result)
        assert strategy == DataStrategy.INLINE
        assert len(data) == 2


# ---------------------------------------------------------------------------
# NOOA Agent instantiation tests
# ---------------------------------------------------------------------------

class TestNOOAAgents:
    def test_schema_agent_instantiates(self):
        mock_pool = MagicMock()
        agent = SchemaAgent()
        agent.pool = mock_pool
        assert agent.pool is mock_pool
        assert agent.get_cached() is None

    def test_schema_agent_caching(self):
        agent = SchemaAgent()
        agent.pool = MagicMock()
        schema = SchemaMap(tables=["t1"], columns={"t1": []})
        agent.set_cache(schema)
        assert agent.get_cached() is schema

    def test_sql_agent_instantiates(self):
        mock_pool = MagicMock()
        agent = SQLAgent()
        agent.pool = mock_pool
        assert agent.pool is mock_pool

    def test_sql_agent_validate_sql_ok(self):
        agent = SQLAgent()
        agent.pool = MagicMock()
        assert agent.validate_sql("SELECT 1") == "OK"

    def test_sql_agent_validate_sql_rejects(self):
        agent = SQLAgent()
        agent.pool = MagicMock()
        result = agent.validate_sql("DROP TABLE users")
        assert "read-only" in result

    def test_viz_agent_instantiates(self):
        agent = VizAgent()
        assert agent is not None

    def test_viz_agent_plan_chart_temporal(self):
        agent = VizAgent()
        rows = [
            {"month": "2024-01-01", "revenue": 100},
            {"month": "2024-02-01", "revenue": 200},
        ]
        result = QueryResult(columns=["month", "revenue"], rows=rows, row_count=2)
        plan = agent.plan_chart("Show monthly revenue", result)
        assert plan.chart_type == ChartType.LINE
        assert plan.x_field == "month"
        assert plan.y_field == "revenue"

    def test_viz_agent_plan_chart_categorical(self):
        agent = VizAgent()
        rows = [
            {"region": "North", "sales": 100},
            {"region": "South", "sales": 200},
        ]
        result = QueryResult(columns=["region", "sales"], rows=rows, row_count=2)
        plan = agent.plan_chart("Sales by region", result)
        assert plan.chart_type == ChartType.BAR
        assert plan.x_field == "region"
        assert plan.y_field == "sales"

    def test_coordinator_agent_instantiates(self):
        agent = CoordinatorAgent()
        agent.schema_agent = SchemaAgent()
        agent.schema_agent.pool = MagicMock()
        agent.sql_agent = SQLAgent()
        agent.sql_agent.pool = MagicMock()
        agent.viz_agent = VizAgent()
        agent.cache = QueryCache()
        agent.connection_id = "test"
        assert agent.connection_id == "test"


# ---------------------------------------------------------------------------
# Coordinator pipeline tests
# ---------------------------------------------------------------------------

class TestCoordinatorPipeline:
    def _make_coordinator(self) -> CoordinatorAgent:
        agent = CoordinatorAgent()
        agent.schema_agent = SchemaAgent()
        agent.schema_agent.pool = MagicMock()
        agent.sql_agent = SQLAgent()
        agent.sql_agent.pool = MagicMock()
        agent.viz_agent = VizAgent()
        agent.cache = QueryCache()
        agent.connection_id = "test"
        return agent

    def test_cache_hit_returns_stored_result(self):
        """A cache hit must return the stored result without re-running the pipeline."""
        agent = self._make_coordinator()
        rows = [{"month": "2024-01-01", "revenue": 100}]
        result = QueryResult(
            columns=["month", "revenue"],
            rows=rows,
            row_count=1,
            sql="SELECT month, revenue FROM subscriptions",
            execution_time_ms=12.5,
        )
        agent.cache.put(cache_key("test", "show monthly revenue"), result)

        # Pipeline must not touch the DB or LLM on a cache hit — use stubs that
        # would fail loudly if called. NOOA's method guard forbids attaching
        # callables to agent instances, so use plain stub objects instead.
        class StubSchema:
            async def fetch_schema(self):
                raise AssertionError("schema fetched on cache hit")

        class StubSQL:
            async def generate(self, question, schema):
                raise AssertionError("sql generated on cache hit")

        agent.schema_agent = StubSchema()
        agent.sql_agent = StubSQL()

        async def collect():
            return [e async for e in agent.run("show monthly revenue")]

        events = asyncio.run(collect())
        result_events = [e for e in events if e["type"] == "result"]
        assert len(result_events) == 1
        event = result_events[0]
        assert event["cached"] is True
        assert event["row_count"] == 1
        assert event["sql"] == "SELECT month, revenue FROM subscriptions"
        assert event["chart_spec"]["plan"]["chart_type"] == "line"

    def test_cache_miss_runs_pipeline(self):
        """A cache miss must run the full pipeline and store the result."""
        agent = self._make_coordinator()
        rows = [{"region": "North", "sales": 100}]
        result = QueryResult(
            columns=["region", "sales"],
            rows=rows,
            row_count=1,
            sql="SELECT region, sales FROM accounts",
            execution_time_ms=5.0,
        )

        class StubSchema:
            async def fetch_schema(self):
                return SchemaMap(tables=["accounts"], columns={"accounts": []})

        class StubSQL:
            async def generate(self, question, schema):
                return GeneratedSQL(sql="SELECT region, sales FROM accounts")

            async def execute_query(self, sql):
                return result

        class StubViz:
            def plan_chart(self, question, result):
                return VizAgent().plan_chart(question, result)

            def build_vega_lite(self, plan, result):
                return VizAgent().build_vega_lite(plan, result)

        agent.schema_agent = StubSchema()
        agent.sql_agent = StubSQL()
        agent.viz_agent = StubViz()

        async def collect():
            return [e async for e in agent.run("sales by region")]

        events = asyncio.run(collect())
        result_events = [e for e in events if e["type"] == "result"]
        assert len(result_events) == 1
        assert result_events[0]["cached"] is False
        # Result stored for next call
        assert agent.cache.get(cache_key("test", "sales by region")) is not None
