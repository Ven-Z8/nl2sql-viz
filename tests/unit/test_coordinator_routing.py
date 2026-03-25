import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.agents.coordinator import Coordinator


def _make_connector():
    conn = MagicMock()
    conn.execute_read = AsyncMock(return_value=[{"region": "North", "total": 1000}])
    return conn


def _make_session_store(session_id="test-session"):
    store = MagicMock()
    store.get_schema_cache = AsyncMock(return_value=None)
    store.set_schema_cache = AsyncMock()
    return store


@pytest.mark.asyncio
async def test_coordinator_sql_only_path_yields_result():
    """When route is sql_only, result event is yielded without code exec."""
    coordinator = Coordinator(
        connector=_make_connector(),
        session_store=_make_session_store(),
        session_id="test-session",
    )

    with (
        patch.object(coordinator, "_decide_route", AsyncMock(return_value="sql_only")),
        patch("app.agents.coordinator.SchemaAgent") as MockSchema,
        patch("app.agents.coordinator.SQLAgent") as MockSQL,
        patch("app.agents.coordinator.VizAgent") as MockViz,
        patch("app.agents.coordinator.CodeExecAgent") as MockCode,
    ):
        MockSchema.return_value.get_schema_map = AsyncMock(return_value="sales(region:text)")
        MockSQL.return_value.run = AsyncMock(return_value={
            "status": "success", "sql": "SELECT region FROM sales", "rows": [{"region": "North"}]
        })
        MockViz.return_value.run = AsyncMock(return_value='{"$schema": "vega"}')

        events = [e async for e in coordinator.run("top regions")]

    event_types = [e["type"] for e in events]
    assert "result" in event_types
    MockCode.assert_not_called()


@pytest.mark.asyncio
async def test_coordinator_needs_transform_path_calls_code_exec():
    """When route is needs_transform, CodeExecAgent is called after SQL."""
    coordinator = Coordinator(
        connector=_make_connector(),
        session_store=_make_session_store(),
        session_id="test-session",
    )

    transformed_rows = [{"region": "North", "pct": 0.6}]

    with (
        patch.object(coordinator, "_decide_route", AsyncMock(return_value="needs_transform")),
        patch("app.agents.coordinator.SchemaAgent") as MockSchema,
        patch("app.agents.coordinator.SQLAgent") as MockSQL,
        patch("app.agents.coordinator.VizAgent") as MockViz,
        patch("app.agents.coordinator.CodeExecAgent") as MockCode,
    ):
        MockSchema.return_value.get_schema_map = AsyncMock(return_value="sales(region:text)")
        MockSQL.return_value.run = AsyncMock(return_value={
            "status": "success", "sql": "SELECT region FROM sales", "rows": [{"region": "North"}]
        })
        MockCode.return_value.run = AsyncMock(return_value={
            "status": "success", "rows": transformed_rows, "code": "const result = rows;"
        })
        MockViz.return_value.run = AsyncMock(return_value='{"$schema": "vega"}')

        events = [e async for e in coordinator.run("calculate percentages")]

    event_types = [e["type"] for e in events]
    assert "result" in event_types
    MockCode.return_value.run.assert_called_once()
    viz_call_rows = MockViz.return_value.run.call_args.kwargs["rows"]
    assert viz_call_rows == transformed_rows


@pytest.mark.asyncio
async def test_coordinator_falls_back_to_sql_rows_on_code_exec_error():
    """On CodeExecAgent error, Coordinator falls back to raw SQL rows."""
    coordinator = Coordinator(
        connector=_make_connector(),
        session_store=_make_session_store(),
        session_id="test-session",
    )

    original_rows = [{"region": "North", "amount": 1000}]

    with (
        patch.object(coordinator, "_decide_route", AsyncMock(return_value="needs_transform")),
        patch("app.agents.coordinator.SchemaAgent") as MockSchema,
        patch("app.agents.coordinator.SQLAgent") as MockSQL,
        patch("app.agents.coordinator.VizAgent") as MockViz,
        patch("app.agents.coordinator.CodeExecAgent") as MockCode,
    ):
        MockSchema.return_value.get_schema_map = AsyncMock(return_value="sales(region:text)")
        MockSQL.return_value.run = AsyncMock(return_value={
            "status": "success", "sql": "SELECT * FROM sales", "rows": original_rows
        })
        MockCode.return_value.run = AsyncMock(return_value={
            "status": "error", "message": "ReferenceError: result is not defined"
        })
        MockViz.return_value.run = AsyncMock(return_value='{"$schema": "vega"}')

        events = [e async for e in coordinator.run("complex transform")]

    event_types = [e["type"] for e in events]
    assert "result" in event_types
    viz_call_rows = MockViz.return_value.run.call_args.kwargs["rows"]
    assert viz_call_rows == original_rows
