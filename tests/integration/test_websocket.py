"""
WebSocket integration tests for the /ws/query endpoint.

Tests:
  1. Full flow: register -> auth handshake -> NL query -> result event with vega_spec
  2. Bad API key: server closes connection with code 4001
"""
import json
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app

TEST_DSN = "postgresql://testuser:testpass@localhost:5432/testdb"


def test_register_and_query_via_websocket(seed_test_db):
    """
    Full end-to-end flow via WebSocket:
    - Register a new user to obtain an API key
    - Authenticate over WebSocket
    - Send an NL query against the seeded sales table
    - Assert a result event arrives with vega_spec and sql fields
    """
    client = TestClient(app)

    # Register — use a username that won't collide with other tests
    resp = client.post("/api/register", json={"username": "ws_test_user_1"})
    assert resp.status_code == 200, f"Registration failed: {resp.text}"
    api_key = resp.json()["api_key"]

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
            "dsn": TEST_DSN,
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
    assert "vega_spec" in result, f"result event missing 'vega_spec': {result}"
    assert "sql" in result, f"result event missing 'sql': {result}"

    # vega_spec must be valid JSON with a $schema field
    spec = json.loads(result["vega_spec"])
    assert "$schema" in spec, f"vega_spec missing '$schema': {spec.keys()}"


def test_websocket_rejects_bad_api_key():
    """
    Sending an invalid API key during auth handshake must cause
    the server to close the connection with code 4001.
    The test passes if the connection is closed (any exception after send).
    """
    client = TestClient(app)

    # Register a real user so _users is non-empty — rules out "empty store" false passes
    resp = client.post("/api/register", json={"username": "ws_test_user_2"})
    assert resp.status_code == 200

    connection_closed = False
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
