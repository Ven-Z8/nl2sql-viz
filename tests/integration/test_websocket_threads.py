"""Contract V3 integration-style tests: conversation threads over /ws/query.

Runs the REAL WebSocket handler in app.main with the CoordinatorAgent mocked,
so no LLM is called. Asserts:
  - thread_id echo / generation + 1-based turn_index on result events
  - is_follow_up morph signal only when the CLIENT supplied a thread_id
  - follow-up context block reaches the pipeline (captured off the fake)
  - stateless path (no thread_id) is unchanged: empty context
  - foreign thread ids start fresh silently (no error leak)
  - clarify round-trips carry the thread id and land on the pending turn
"""
import asyncio
import uuid

import pytest
from starlette.testclient import TestClient

import app.main as app_main
from app.core.connections import register as register_connection
from app.core.threads import get_thread_store
from app.main import app

TEST_DSN = "postgresql://testuser:testpass@localhost:5432/testdb"


# ----------------------------------------------------------------------
# Mocked pipeline — captures what main.py injects per query
# ----------------------------------------------------------------------

def _fake_result(query: str) -> dict:
    return {
        "type": "result",
        "query": query,
        "sql": f"SELECT region, SUM(amount) FROM sales GROUP BY region -- {query}",
        "answer": {"text": "stub"},
        "rows": [
            {"region": "North", "amount": 2500.0},
            {"region": "South", "amount": 1800.0},
            {"region": "East", "amount": 800.0},
        ],
        "row_count": 3,
        "execution_time_ms": 4,
        "cached": False,
        "chart_hint": {"kind": "bar", "title": "By region"},
        "queries": [{"sql": "SELECT ...", "row_count": 3}],
        "provenance": None,
    }


class FakeCoordinator:
    """Drop-in stand-in for CoordinatorAgent — no LLM, no DB work."""

    instances: list["FakeCoordinator"] = []
    ask_in_run: bool = False

    def __init__(self) -> None:
        self.conversation_context = ""
        self.nl_query: str | None = None
        FakeCoordinator.instances.append(self)

    def __getattr__(self, name):  # tolerate any agent wiring main.py performs
        return None

    async def run(self, nl_query: str, ask_user=None):
        self.nl_query = nl_query
        yield {"type": "progress", "stage": "schema", "message": "fake"}
        if FakeCoordinator.ask_in_run and ask_user is not None:
            await ask_user(
                "Which table should the analysis focus on?", ["sales", "customers"]
            )
        yield _fake_result(nl_query)


@pytest.fixture(autouse=True)
def _isolated_state(monkeypatch):
    """Fresh threads + fresh mock instances per test; mock the real pipeline.

    Also takes this module out of the suite-wide auth rate-limit economy:
    registration bursts share ONE rolling per-IP window (5/60s from
    TestClient's host), so these tests would otherwise be victims of — and
    contributors to — spurious 429s in later files (e.g. demo routes).
    """
    get_thread_store().reset()
    FakeCoordinator.instances.clear()
    FakeCoordinator.ask_in_run = False
    monkeypatch.setattr(app_main, "CoordinatorAgent", FakeCoordinator)
    # Skip the throttle AND its timestamp bookkeeping for this module only.
    monkeypatch.setattr(app_main, "_check_ip_rate_limit", lambda request: None)
    yield
    get_thread_store().reset()


# ----------------------------------------------------------------------
# WS helpers
# ----------------------------------------------------------------------

def _drain_until(ws, kinds=("result", "error"), limit=30) -> dict:
    for _ in range(limit):
        event = ws.receive_json()
        if event.get("type") in kinds:
            return event
    raise AssertionError(f"never received {kinds}")


def _make_user_and_connection(client: TestClient) -> tuple[str, str]:
    """Register a user + a server-side connection owned by them."""
    username = f"ws_thr_{uuid.uuid4().hex[:8]}"
    resp = client.post("/api/register", json={"username": username})
    assert resp.status_code == 200, resp.text
    api_key = resp.json()["api_key"]
    # REST /api/connections would dial Postgres first; register() skips that.
    connection_id = asyncio.run(register_connection(TEST_DSN, owner=username))
    return api_key, connection_id


# ----------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------

def test_thread_echo_turn_index_and_followup_signal():
    with TestClient(app) as client:
        api_key, connection_id = _make_user_and_connection(client)

        with client.websocket_connect("/ws/query") as ws:
            ws.send_json({"type": "auth", "api_key": api_key})
            assert ws.receive_json()["type"] == "authenticated"

            # Turn 1 — no thread_id supplied: server mints one.
            ws.send_json({"type": "query", "query": "total sales by region",
                          "connection_id": connection_id})
            r1 = _drain_until(ws)
            assert r1["type"] == "result", r1
            assert isinstance(r1["thread_id"], str) and len(r1["thread_id"]) == 36
            assert r1["turn_index"] == 1
            assert r1["is_follow_up"] is False
            thread_id = r1["thread_id"]

            # Turn 2 — client echoes the thread: same thread, next index.
            ws.send_json({"type": "query", "query": "what about 2019?",
                          "connection_id": connection_id, "thread_id": thread_id})
            r2 = _drain_until(ws)
            assert r2["type"] == "result", r2
            assert r2["thread_id"] == thread_id
            assert r2["turn_index"] == 2
            assert r2["is_follow_up"] is True

    # Follow-up context reached the pipeline on turn 2 only.
    ctx_first = FakeCoordinator.instances[0].conversation_context
    ctx_second = FakeCoordinator.instances[1].conversation_context
    assert ctx_first == ""  # nothing before turn 1
    assert "total sales by region" in ctx_second
    assert "Turn 1" in ctx_second

    # Both turns were recorded in the store under the same thread.
    turns = get_thread_store()._threads[thread_id].turns
    assert [t.index for t in turns] == [1, 2]
    assert turns[0].question == "total sales by region"
    assert "region" in turns[0].compact_summary  # columns + example values


def test_stateless_path_unchanged_without_thread_id():
    with TestClient(app) as client:
        api_key, connection_id = _make_user_and_connection(client)

        with client.websocket_connect("/ws/query") as ws:
            ws.send_json({"type": "auth", "api_key": api_key})
            ws.receive_json()
            ws.send_json({"type": "query", "query": "top 5 regions",
                          "connection_id": connection_id})
            r = _drain_until(ws)

    assert r["type"] == "result"
    assert r["is_follow_up"] is False          # never supplied → never a follow-up
    assert isinstance(r["thread_id"], str)     # V3 still stamps identity
    assert r["turn_index"] == 1
    assert FakeCoordinator.instances[0].conversation_context == ""  # no prompt change


def test_foreign_thread_id_starts_fresh_without_error():
    with TestClient(app) as client:
        alice_key, alice_conn = _make_user_and_connection(client)

        with client.websocket_connect("/ws/query") as ws:
            ws.send_json({"type": "auth", "api_key": alice_key})
            ws.receive_json()
            ws.send_json({"type": "query", "query": "q1", "connection_id": alice_conn})
            alice_result = _drain_until(ws)
        alice_tid = alice_result["thread_id"]

        # Mallory replays Alice's thread id — must start her OWN fresh thread.
        mallory_key, mallory_conn = _make_user_and_connection(client)
        with client.websocket_connect("/ws/query") as ws:
            ws.send_json({"type": "auth", "api_key": mallory_key})
            ws.receive_json()
            ws.send_json({"type": "query", "query": "q2",
                          "connection_id": mallory_conn, "thread_id": alice_tid})
            r = _drain_until(ws)

    assert r["type"] == "result"               # no error event leaked
    assert r["thread_id"] != alice_tid         # fresh thread, silently
    assert r["turn_index"] == 1                # Alice's history not visible
    assert r["is_follow_up"] is True           # client DID supply an id
    # Alice's thread untouched.
    assert len(get_thread_store()._threads[alice_tid].turns) == 1


def test_clarify_roundtrip_joins_thread_and_updates_pending_turn():
    FakeCoordinator.ask_in_run = True
    with TestClient(app) as client:
        api_key, connection_id = _make_user_and_connection(client)

        with client.websocket_connect("/ws/query") as ws:
            ws.send_json({"type": "auth", "api_key": api_key})
            ws.receive_json()

            # Turn 1 establishes the thread.
            ws.send_json({"type": "query", "query": "show me the totals",
                          "connection_id": connection_id})
            r1 = _drain_until(ws)
            thread_id = r1["thread_id"]

            # Turn 2 triggers the mocked clarify round-trip.
            ws.send_json({"type": "query", "query": "split it further",
                          "connection_id": connection_id, "thread_id": thread_id})
            clarify = _drain_until(ws, kinds=("clarify",))
            assert clarify["question"].startswith("Which table")
            assert clarify["options"] == ["sales", "customers"]
            assert clarify["thread_id"] == thread_id  # joins the SAME thread

            ws.send_json({"type": "clarification_response", "choice": 0})
            r2 = _drain_until(ws)

    assert r2["type"] == "result"
    assert r2["thread_id"] == thread_id        # clarification continues the thread
    assert r2["turn_index"] == 2
    # The clarify outcome landed on the pending (second) turn's record.
    turns = get_thread_store()._threads[thread_id].turns
    assert turns[0].clarification is None
    assert "Which table" in (turns[1].clarification or "")
    assert "-> sales" in (turns[1].clarification or "")
