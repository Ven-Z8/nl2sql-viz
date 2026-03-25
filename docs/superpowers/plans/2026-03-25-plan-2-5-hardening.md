# Plan 2.5 — Hardening Sprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three structural issues that will compound under load before building Plan 3 (real-time) features on a shaky foundation.

**Architecture:** (1) Replace blocking `Anthropic()` sync clients with `AsyncAnthropic()` in SQLAgent and VizAgent so Claude API calls don't block the FastAPI event loop. (2) Move the in-memory `_users` dict in `main.py` to a SQLite-backed store so users survive server restarts. (3) Wrap each WebSocket query in a 30-second wall-clock timeout and a per-session rate limit so one stuck query can't hang the server.

**Tech Stack:** Python 3.12, FastAPI, asyncio, `anthropic` SDK (AsyncAnthropic), `aiosqlite`, `unittest.mock.AsyncMock`, pytest

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `app/agents/sql_agent.py` | Switch to `AsyncAnthropic`, `await` the API call |
| Modify | `app/agents/viz_agent.py` | Switch to `AsyncAnthropic`, `await` the API call |
| Modify | `tests/unit/test_viz_agent.py` | Fix patch target + use `AsyncMock` |
| Create | `app/core/user_store.py` | SQLite-backed user store (register, verify, lookup) |
| Modify | `app/main.py` | Use `UserStore`, add query timeout + rate limit |
| Create | `tests/unit/test_user_store.py` | Unit tests for UserStore (in-memory SQLite `:memory:`) |
| Create | `tests/unit/test_request_guard.py` | Tests for timeout + rate limit via `TestClient` WS |

---

## Task 1 — Async Claude Clients (SQLAgent + VizAgent)

**Files:**
- Modify: `app/agents/sql_agent.py:6-10,34`
- Modify: `app/agents/viz_agent.py:6-8,48`
- Modify: `tests/unit/test_viz_agent.py`

### Context

`sql_agent.py` has a **module-level** `_client = Anthropic()` and calls `_client.messages.create(...)` (synchronous) inside an `async def run()`. This blocks the entire FastAPI event loop for the duration of every Claude API call. Same pattern in `viz_agent.py`. The fix: make the client an instance attribute using `AsyncAnthropic()` and `await` the call.

- [ ] **Step 1: Write the failing test for SQLAgent async behavior**

  Add to `tests/unit/test_sql_agent.py` (create if it doesn't exist):

  ```python
  import pytest
  from unittest.mock import AsyncMock, MagicMock, patch
  from app.agents.sql_agent import SQLAgent

  @pytest.mark.asyncio
  async def test_sql_agent_uses_async_client():
      """SQLAgent must use AsyncAnthropic (not sync Anthropic)."""
      from anthropic import AsyncAnthropic
      agent = SQLAgent(connector=MagicMock())
      assert isinstance(agent._client, AsyncAnthropic), (
          "SQLAgent._client must be AsyncAnthropic, not Anthropic"
      )
  ```

- [ ] **Step 2: Run the test to verify it fails**

  ```bash
  cd /Volumes/VeN/Claude-Code-Work/projects/nl2sql-viz
  uv run pytest tests/unit/test_sql_agent.py::test_sql_agent_uses_async_client -v
  ```

  Expected: `AttributeError: 'SQLAgent' object has no attribute '_client'` OR `AssertionError` (currently a module-level client, not instance).

- [ ] **Step 3: Fix `app/agents/sql_agent.py`**

  Replace lines 1–10 and the `messages.create` call:

  ```python
  # Before (lines 1-10):
  from anthropic import Anthropic
  _client = Anthropic()

  class SQLAgent:
      def __init__(self, connector: BaseConnector, max_retries: int = 3):
          self._connector = connector
          self._max_retries = max_retries

  # After:
  from anthropic import AsyncAnthropic

  class SQLAgent:
      def __init__(self, connector: BaseConnector, max_retries: int = 3):
          self._connector = connector
          self._max_retries = max_retries
          self._client = AsyncAnthropic()
  ```

  And the API call (line 34):

  ```python
  # Before:
  response = _client.messages.create(
  # After:
  response = await self._client.messages.create(
  ```

- [ ] **Step 4: Write the failing test for VizAgent async behavior**

  Update `tests/unit/test_viz_agent.py` — replace the existing `patch` targets with `AsyncMock`:

  ```python
  import pytest
  import json
  from unittest.mock import AsyncMock, MagicMock, patch
  from app.agents.viz_agent import VizAgent

  SAMPLE_ROWS = [
      {"region": "North", "total": 2500.00},
      {"region": "South", "total": 2000.00},
      {"region": "East", "total": 800.00},
  ]

  MOCK_VEGA_SPEC = json.dumps({
      "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
      "mark": "bar",
      "data": {"values": SAMPLE_ROWS},
      "encoding": {
          "x": {"field": "region", "type": "nominal"},
          "y": {"field": "total", "type": "quantitative"}
      }
  })


  @pytest.mark.asyncio
  async def test_viz_agent_uses_async_client():
      from anthropic import AsyncAnthropic
      agent = VizAgent()
      assert isinstance(agent._client, AsyncAnthropic)


  @pytest.mark.asyncio
  async def test_viz_agent_returns_valid_vega_spec():
      agent = VizAgent()
      mock_response = MagicMock()
      mock_response.content = [MagicMock(text=MOCK_VEGA_SPEC)]

      agent._client = AsyncMock()
      agent._client.messages.create = AsyncMock(return_value=mock_response)

      spec = await agent.run(nl_query="Total sales by region", rows=SAMPLE_ROWS)

      parsed = json.loads(spec)
      assert "$schema" in parsed
      assert "mark" in parsed
      assert "data" in parsed
      assert "encoding" in parsed


  @pytest.mark.asyncio
  async def test_viz_agent_raises_on_invalid_json():
      agent = VizAgent()
      mock_response = MagicMock()
      mock_response.content = [MagicMock(text="not valid json {{{")]

      agent._client = AsyncMock()
      agent._client.messages.create = AsyncMock(return_value=mock_response)

      with pytest.raises(ValueError, match="Invalid Vega-Lite JSON"):
          await agent.run(nl_query="test", rows=[])
  ```

- [ ] **Step 5: Run VizAgent tests to verify they fail**

  ```bash
  uv run pytest tests/unit/test_viz_agent.py -v
  ```

  Expected: `AttributeError: 'VizAgent' object has no attribute '_client'`.

- [ ] **Step 6: Fix `app/agents/viz_agent.py`**

  ```python
  # Remove module-level client (lines 6-8):
  # DELETE: from anthropic import Anthropic
  # DELETE: _client = Anthropic()

  # Add to imports:
  from anthropic import AsyncAnthropic

  class VizAgent:
      def __init__(self) -> None:
          self._client = AsyncAnthropic()

      async def run(self, nl_query: str, rows: list[dict[str, Any]]) -> str:
          ...
          # Change line 48:
          response = await self._client.messages.create(
  ```

- [ ] **Step 7: Run all unit tests to verify everything passes**

  ```bash
  uv run pytest tests/unit/ -v
  ```

  Expected: All pass. In particular:
  - `test_sql_agent_uses_async_client` — PASS
  - `test_viz_agent_uses_async_client` — PASS
  - `test_viz_agent_returns_valid_vega_spec` — PASS
  - `test_viz_agent_raises_on_invalid_json` — PASS

- [ ] **Step 8: Also fix SQLAgent test for the API call itself**

  Add to `tests/unit/test_sql_agent.py`:

  ```python
  @pytest.mark.asyncio
  async def test_sql_agent_returns_sql_on_success():
      """SQLAgent.run() returns status=success with sql and rows."""
      mock_connector = AsyncMock()
      mock_connector.execute_read = AsyncMock(return_value=[{"count": 3}])

      agent = SQLAgent(connector=mock_connector)
      mock_response = MagicMock()
      mock_response.content = [MagicMock(text="SELECT COUNT(*) FROM sales")]
      agent._client = AsyncMock()
      agent._client.messages.create = AsyncMock(return_value=mock_response)

      result = await agent.run(nl_query="How many sales?", schema_map="sales(id, amount)")
      assert result["status"] == "success"
      assert "SELECT" in result["sql"]
      assert result["rows"] == [{"count": 3}]
  ```

- [ ] **Step 9: Run full test suite**

  ```bash
  uv run pytest tests/unit/ -v
  ```

  Expected: All pass.

- [ ] **Step 10: Commit**

  ```bash
  git add app/agents/sql_agent.py app/agents/viz_agent.py tests/unit/test_viz_agent.py tests/unit/test_sql_agent.py
  git commit -m "fix: replace sync Anthropic() with AsyncAnthropic() in SQLAgent and VizAgent

  Sync _client.messages.create() inside async def blocks the FastAPI event loop.
  Both agents now use AsyncAnthropic() as an instance attribute with await.
  Tests updated to use AsyncMock and patch at the instance level.

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
  ```

---

## Task 2 — SQLite-Backed User Store

**Files:**
- Create: `app/core/user_store.py`
- Modify: `app/main.py`
- Create: `tests/unit/test_user_store.py`

### Context

`_users: dict[str, str]` in `main.py` is a global in-memory dict mapping `username -> hashed_api_key`. It resets every server restart, meaning every registered user disappears. Replace it with a SQLite-backed `UserStore` that persists to a file (default `data/users.db`). SQLite requires no external service, runs in-process, and is perfect for this use case.

`aiosqlite` provides an async interface to SQLite compatible with FastAPI's event loop.

- [ ] **Step 1: Install aiosqlite**

  ```bash
  uv add aiosqlite
  ```

- [ ] **Step 2: Write failing tests for UserStore**

  Create `tests/unit/test_user_store.py`:

  ```python
  import pytest
  import pytest_asyncio
  from app.core.user_store import UserStore

  @pytest_asyncio.fixture  # Required for pytest-asyncio >= 0.21 (project uses 1.x)
  async def store(tmp_path):
      """File-based SQLite store via pytest's tmp_path (auto-cleaned after each test).

      IMPORTANT: UserStore opens a new aiosqlite.connect() per operation.
      With ":memory:", each call gets a separate empty database — the table
      created by init() would disappear immediately. Use a real temp file instead.
      pytest's tmp_path provides a unique directory per test, cleaned up automatically.
      """
      s = UserStore(db_path=str(tmp_path / "test_users.db"))
      await s.init()
      return s


  @pytest.mark.asyncio
  async def test_register_and_verify(store):
      await store.register("alice", "hash_abc")
      assert await store.exists("alice") is True
      assert await store.get_hashed_key("alice") == "hash_abc"


  @pytest.mark.asyncio
  async def test_register_duplicate_raises(store):
      await store.register("bob", "hash_xyz")
      with pytest.raises(ValueError, match="already exists"):
          await store.register("bob", "hash_other")


  @pytest.mark.asyncio
  async def test_verify_all_users(store):
      await store.register("carol", "hash_carol")
      await store.register("dave", "hash_dave")
      users = await store.all_users()
      assert ("carol", "hash_carol") in users
      assert ("dave", "hash_dave") in users


  @pytest.mark.asyncio
  async def test_nonexistent_user_returns_none(store):
      assert await store.get_hashed_key("nobody") is None
      assert await store.exists("nobody") is False
  ```

- [ ] **Step 3: Run tests to verify they fail**

  ```bash
  uv run pytest tests/unit/test_user_store.py -v
  ```

  Expected: `ModuleNotFoundError: No module named 'app.core.user_store'`

- [ ] **Step 4: Implement `app/core/user_store.py`**

  ```python
  import sqlite3

  import aiosqlite
  from pathlib import Path
  from typing import Optional


  class UserStore:
      """Persistent user store backed by SQLite.

      Args:
          db_path: Path to SQLite file. Default: "data/users.db".
                   For testing, use a temp file (e.g. pytest's tmp_path / "test.db").
                   Do NOT use ":memory:" — each aiosqlite.connect() call opens
                   a separate in-process database, so the table created by init()
                   would be invisible to all subsequent method calls.
      """

      def __init__(self, db_path: str = "data/users.db") -> None:
          self._db_path = db_path

      async def init(self) -> None:
          """Create the users table if it doesn't exist."""
          if self._db_path != ":memory:":
              Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
          async with aiosqlite.connect(self._db_path) as db:
              await db.execute(
                  """CREATE TABLE IF NOT EXISTS users (
                      username TEXT PRIMARY KEY,
                      hashed_key TEXT NOT NULL
                  )"""
              )
              await db.commit()

      async def register(self, username: str, hashed_key: str) -> None:
          """Register a new user. Raises ValueError if username already exists."""
          async with aiosqlite.connect(self._db_path) as db:
              try:
                  await db.execute(
                      "INSERT INTO users (username, hashed_key) VALUES (?, ?)",
                      (username, hashed_key),
                  )
                  await db.commit()
              except sqlite3.IntegrityError:
                  # aiosqlite raises standard sqlite3 exceptions — NOT aiosqlite.IntegrityError.
                  # Always catch sqlite3.IntegrityError for constraint violations.
                  raise ValueError(f"User '{username}' already exists")

      async def get_hashed_key(self, username: str) -> Optional[str]:
          """Return the stored hashed key for username, or None."""
          async with aiosqlite.connect(self._db_path) as db:
              async with db.execute(
                  "SELECT hashed_key FROM users WHERE username = ?", (username,)
              ) as cursor:
                  row = await cursor.fetchone()
                  return row[0] if row else None

      async def exists(self, username: str) -> bool:
          return await self.get_hashed_key(username) is not None

      async def all_users(self) -> list[tuple[str, str]]:
          """Return list of (username, hashed_key) tuples — used for auth verification."""
          async with aiosqlite.connect(self._db_path) as db:
              async with db.execute("SELECT username, hashed_key FROM users") as cursor:
                  return await cursor.fetchall()
  ```

- [ ] **Step 5: Run tests to verify they pass**

  ```bash
  uv run pytest tests/unit/test_user_store.py -v
  ```

  Expected: All 4 tests PASS.

- [ ] **Step 6: Wire UserStore into `app/main.py`**

  Replace the global `_users` dict and all references:

  ```python
  # Add import:
  from app.core.user_store import UserStore

  # Replace module-level dict:
  # DELETE: _users: dict[str, str] = {}
  user_store = UserStore()  # default: data/users.db

  # Update lifespan to call init():
  @asynccontextmanager
  async def lifespan(app: FastAPI):
      await user_store.init()
      yield

  # Update /api/register:
  @app.post("/api/register")
  async def register(req: RegisterRequest):
      try:
          api_key = generate_api_key()
          await user_store.register(req.username, hash_api_key(api_key))
          return {"api_key": api_key, "username": req.username}
      except ValueError:
          raise HTTPException(status_code=409, detail="Username already exists")

  # Update _verify_api_key_or_raise():
  def _verify_api_key_or_raise(api_key: str) -> str:
      # NOTE: This function needs to become async since user_store is async.
      # Rename to async and update all callers.
      raise NotImplementedError("see step below")
  ```

  The full updated `main.py` auth section:

  ```python
  async def _verify_api_key_or_raise(api_key: str) -> str:
      for username, hashed in await user_store.all_users():
          if verify_api_key(api_key, hashed):
              return username
      raise HTTPException(status_code=401, detail="Invalid API key")
  ```

  There are **two** callers of `_verify_api_key_or_raise` in `main.py` — both must be updated:

  1. `connect_db` (line 52): `_verify_api_key_or_raise(req.api_key)` → `await _verify_api_key_or_raise(req.api_key)`
  2. The WebSocket auth loop does NOT call this function — it has an inline loop. Update that inline loop as shown below.

  In the WebSocket handler, replace the inline auth loop:

  ```python
  # Before (lines 81-86):
  user_id = None
  for uid, hashed in _users.items():
      if verify_api_key(auth_msg["api_key"], hashed):
          user_id = uid
          break
  if not user_id:
      ...

  # After:
  user_id = None
  for username, hashed in await user_store.all_users():
      if verify_api_key(auth_msg["api_key"], hashed):
          user_id = username
          break
  if not user_id:
      ...
  ```

- [ ] **Step 7: Run the full unit test suite**

  ```bash
  uv run pytest tests/unit/ -v
  ```

  Expected: All pass (existing tests should be unaffected since they don't touch `_users`).

- [ ] **Step 8: Smoke test the server**

  ```bash
  uv run uvicorn app.main:app --reload --port 8000 &
  sleep 2
  curl -s -X POST http://localhost:8000/api/register \
    -H "Content-Type: application/json" \
    -d '{"username": "testuser"}' | python3 -m json.tool
  # Expected: {"api_key": "nlq_...", "username": "testuser"}

  # Check DB file was created:
  ls -la data/users.db
  kill %1
  ```

- [ ] **Step 9: Commit**

  ```bash
  git add app/core/user_store.py app/main.py tests/unit/test_user_store.py
  git commit -m "feat: replace in-memory _users dict with SQLite-backed UserStore

  Users now persist across server restarts via aiosqlite (data/users.db).
  UserStore.init() called in FastAPI lifespan to ensure schema exists before
  the first request. _verify_api_key_or_raise() made async to match.

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
  ```

---

## Task 3 — Per-Request Timeout + Rate Limit

**Files:**
- Modify: `app/main.py`
- Create: `tests/unit/test_request_guard.py`

### Context

The WebSocket query handler has no timeout. A single stuck query (bad SQL, Claude API delay, Postgres lock) will hold the connection forever and block the session for that user indefinitely. Additionally, there's no rate limit — a client can fire unlimited concurrent queries.

**Timeout strategy:** `asyncio.wait_for` doesn't work directly on `async for` loops. The correct approach is to run the entire query-processing block as a `asyncio.Task` and cancel it after a deadline.

**Rate limit strategy:** Simple token bucket per session — track the timestamp of the last N queries. If more than `RATE_LIMIT_QUERIES` queries have been submitted within `RATE_LIMIT_WINDOW_SECONDS`, reject with an error event. No external dependency needed.

- [ ] **Step 1: Write failing tests**

  Create `tests/unit/test_request_guard.py`:

  ```python
  import asyncio
  import pytest
  from unittest.mock import AsyncMock, MagicMock, patch
  from collections import deque
  import time

  # We test the guard logic in isolation — not the full WS handler.
  # Import the helpers once they exist.
  from app.main import _check_rate_limit, RATE_LIMIT_QUERIES, RATE_LIMIT_WINDOW_SECONDS


  def test_rate_limit_allows_under_threshold():
      timestamps: deque = deque()
      for _ in range(RATE_LIMIT_QUERIES - 1):
          timestamps.append(time.monotonic() - 1)
      # Should NOT raise
      _check_rate_limit(timestamps)


  def test_rate_limit_blocks_at_threshold():
      timestamps: deque = deque()
      now = time.monotonic()
      for _ in range(RATE_LIMIT_QUERIES):
          timestamps.append(now - 1)  # all within the window
      with pytest.raises(RuntimeError, match="Rate limit"):
          _check_rate_limit(timestamps)


  def test_rate_limit_resets_after_window():
      timestamps: deque = deque()
      old = time.monotonic() - RATE_LIMIT_WINDOW_SECONDS - 1
      for _ in range(RATE_LIMIT_QUERIES):
          timestamps.append(old)  # all outside the window
      # Should NOT raise (old timestamps expire)
      _check_rate_limit(timestamps)
  ```

- [ ] **Step 2: Run tests to verify they fail**

  ```bash
  uv run pytest tests/unit/test_request_guard.py -v
  ```

  Expected: `ImportError: cannot import name '_check_rate_limit' from 'app.main'`

- [ ] **Step 3: Add three missing imports to `app/main.py`**

  The current `main.py` does NOT import `asyncio`, `time`, or `collections.deque`. All three are required. Add them unconditionally to the import section at the top of the file:

  ```python
  import asyncio
  import time
  from collections import deque
  ```

- [ ] **Step 4: Add constants and `_check_rate_limit` to `app/main.py`**

  After the imports, add:

  ```python
  QUERY_TIMEOUT_SECONDS = 30
  RATE_LIMIT_QUERIES = 10       # max queries per window
  RATE_LIMIT_WINDOW_SECONDS = 60  # rolling window in seconds


  def _check_rate_limit(timestamps: deque) -> None:
      """Raise RuntimeError if too many queries in the rolling window.

      Mutates `timestamps` — removes expired entries, then checks count.
      """
      now = time.monotonic()
      # Evict expired entries from the left
      while timestamps and now - timestamps[0] > RATE_LIMIT_WINDOW_SECONDS:
          timestamps.popleft()
      if len(timestamps) >= RATE_LIMIT_QUERIES:
          raise RuntimeError(
              f"Rate limit: max {RATE_LIMIT_QUERIES} queries per {RATE_LIMIT_WINDOW_SECONDS}s"
          )
  ```

- [ ] **Step 5: Run rate limit tests to verify they pass**

  ```bash
  uv run pytest tests/unit/test_request_guard.py -v
  ```

  Expected: All 3 PASS.

- [ ] **Step 6: Wire timeout + rate limit into the WebSocket handler**

  Replace the query-handling section in `websocket_query()`:

  ```python
  # Add per-session rate limit tracker (outside the query loop, inside the WS handler):
  query_timestamps: deque = deque()

  # Replace the query handling block:
  while True:
      data = await websocket.receive_json()
      if data.get("type") != "query":
          continue

      nl_query = data.get("query", "").strip()
      dsn = data.get("dsn", "")
      if not nl_query or not dsn:
          await websocket.send_json({"type": "error", "message": "query and dsn required"})
          continue

      # Rate limit check
      try:
          _check_rate_limit(query_timestamps)
      except RuntimeError as e:
          await websocket.send_json({"type": "error", "message": str(e)})
          continue
      query_timestamps.append(time.monotonic())

      # Per-query timeout
      connector = PostgresConnector(dsn=dsn)
      try:
          await connector.connect()
          coordinator = Coordinator(
              connector=connector,
              session_store=session_store,
              session_id=session_id,
          )

          async def _run_query():
              async for event in coordinator.run(nl_query):
                  await websocket.send_json(event)

          try:
              await asyncio.wait_for(_run_query(), timeout=QUERY_TIMEOUT_SECONDS)
          except asyncio.TimeoutError:
              await websocket.send_json({
                  "type": "error",
                  "message": f"Query timed out after {QUERY_TIMEOUT_SECONDS}s",
              })
      except Exception as e:
          await websocket.send_json({"type": "error", "message": str(e)})
      finally:
          await connector.disconnect()
  ```

- [ ] **Step 7: Run full unit test suite**

  ```bash
  uv run pytest tests/unit/ -v
  ```

  Expected: All pass.

- [ ] **Step 8: Commit**

  ```bash
  git add app/main.py tests/unit/test_request_guard.py
  git commit -m "feat: add 30s query timeout and per-session rate limit to WebSocket handler

  asyncio.wait_for wraps the full async-for query loop in a coroutine.
  _check_rate_limit() uses a deque-based sliding window (10 req / 60s default).
  Both limits are configurable via module-level constants.

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
  ```

---

## Final Verification

- [ ] **Run the complete test suite**

  ```bash
  uv run pytest tests/ -v --ignore=tests/integration --ignore=tests/security
  ```

  Expected: All unit tests pass. Zero failures.

- [ ] **Run integration tests** (requires Postgres running and ANTHROPIC_API_KEY set)

  ```bash
  uv run pytest tests/integration/ -v
  ```

- [ ] **Update `.cursorrules`**

  In the Plan Roadmap table, add a new row:
  ```
  | Plan 2.5 — Hardening Sprint | ✅ Complete | AsyncAnthropic in all agents, SQLite user store, query timeout + rate limit |
  ```

  Under `## What NOT to Do`, add:
  ```
  - **Never** use module-level `Anthropic()` — always use `AsyncAnthropic()` as an instance attribute inside agent classes
  - **Never** store users in `_users: dict` in main.py — use `UserStore` (data/users.db)
  ```

- [ ] **Final commit**

  ```bash
  git add .cursorrules
  git commit -m "docs: mark Plan 2.5 complete in .cursorrules

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
  ```
