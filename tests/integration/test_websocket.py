"""
WebSocket integration tests for the /ws/query endpoint.

Tests:
  1. Full flow: register -> register connection -> auth handshake -> NL query
     -> result event with chart_hint
  2. Bad API key: server closes connection with code 4001
  3. Unknown/foreign connection_id: server sends an "unknown connection" error
"""
import uuid
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app

TEST_DSN = "postgresql://testuser:testpass@localhost:5432/testdb"


def test_register_and_query_via_websocket(seed_test_db):
    """
    Full end-to-end flow via WebSocket:
    - Register a new user to obtain an API key
    - POST /api/connections to store the DSN server-side (never sent over WS)
    - Authenticate over WebSocket
    - Send an NL query against the seeded sales table using connection_id
    - Assert a result event arrives with sql and chart_hint fields
    """
    with TestClient(app) as client:
        # Register with a unique username to avoid collisions with persistent SQLite store
        username = f"ws_test_{uuid.uuid4().hex[:8]}"
        resp = client.post("/api/register", json={"username": username})
        assert resp.status_code == 200, f"Registration failed: {resp.text}"
        api_key = resp.json()["api_key"]

        conn_resp = client.post("/api/connections", json={"api_key": api_key, "dsn": TEST_DSN})
        assert conn_resp.status_code == 200, f"Connection registration failed: {conn_resp.text}"
        connection_id = conn_resp.json()["connection_id"]

        with client.websocket_connect("/ws/query") as ws:
            # Auth handshake
            ws.send_json({"type": "auth", "api_key": api_key})
            auth_resp = ws.receive_json()
            assert auth_resp["type"] == "authenticated", (
                f"Expected 'authenticated', got: {auth_resp}"
            )

            # Send NL query against the seeded sales table
            ws.send_json({
                "type": "query",
                "query": "What is the total sales amount per region?",
                "connection_id": connection_id,
            })

            # Collect events until result or error arrives (up to 20 messages)
            # No timeout kwarg — TestClient.timeout=60 covers the blocking receive calls
            events = []
            for _ in range(20):
                try:
                    event = ws.receive_json()
                    events.append(event)
                    if event["type"] in ("result", "error"):
                        break
                except WebSocketDisconnect:
                    break

    event_types = [e["type"] for e in events]
    assert "result" in event_types, (
        f"Expected a 'result' event but only received: {event_types}"
    )

    result = next(e for e in events if e["type"] == "result")
    # Contract: chart_hint replaces the old chart_spec field
    assert "chart_spec" not in result, f"result must not carry chart_spec: {result.keys()}"
    assert isinstance(result.get("chart_hint"), dict), f"result missing 'chart_hint': {result}"
    assert result["chart_hint"]["kind"] in (
        "bar", "stacked_bar", "grouped_bar", "line", "area",
        "pie", "scatter", "histogram", "kpi",
    )
    assert "sql" in result, f"result event missing 'sql': {result}"
    assert result["query"].startswith("What is the total sales")
    # Contract V2 additions: every shipped result set + per-number provenance
    assert isinstance(result.get("queries"), list) and result["queries"], (
        f"result missing 'queries': {result.keys()}"
    )
    assert result["queries"][0]["row_count"] == result["row_count"]
    prov = result.get("provenance")
    assert prov is None or all(
        {"metric", "value", "query_index", "row_index"} <= set(p) for p in prov
    )


def test_websocket_rejects_bad_api_key():
    """
    Sending an invalid API key during auth handshake must cause
    the server to close the connection with code 4001.
    The test passes if the connection is closed (any exception after send).
    """
    connection_closed = False
    with TestClient(app) as client:
        # Register a real user so _users is non-empty — rules out "empty store" false passes.
        username = f"ws_test_{uuid.uuid4().hex[:8]}"
        resp = client.post("/api/register", json={"username": username})
        assert resp.status_code == 200

        try:
            with client.websocket_connect("/ws/query") as ws:
                ws.send_json({"type": "auth", "api_key": "this-is-not-a-valid-key"})
                # Server should close — any receive attempt must raise
                ws.receive_json()
                # If we get here the server did NOT close — that is the failure
        except (WebSocketDisconnect, RuntimeError):
            connection_closed = True

    assert connection_closed, (
        "Expected server to close WebSocket on bad API key"
    )


def test_websocket_unknown_connection_is_rejected(seed_test_db):
    """A query naming an unregistered connection_id gets a clean error, not a crash."""
    with TestClient(app) as client:
        username = f"ws_test_{uuid.uuid4().hex[:8]}"
        resp = client.post("/api/register", json={"username": username})
        api_key = resp.json()["api_key"]

        with client.websocket_connect("/ws/query") as ws:
            ws.send_json({"type": "auth", "api_key": api_key})
            auth_resp = ws.receive_json()
            assert auth_resp["type"] == "authenticated"

            ws.send_json({
                "type": "query",
                "query": "What is the total sales amount?",
                "connection_id": "0" * 16,  # never registered
            })
            event = ws.receive_json()
            assert event["type"] == "error"
            assert event["message"] == "unknown connection"


def test_health_endpoint():
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
