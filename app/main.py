# app/main.py
import asyncio
import os
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Request, UploadFile, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.core.auth import generate_api_key, hash_api_key, key_digest, verify_api_key
from app.core.connections import (
    get_active_dataset,
    register as register_connection,
    register_demo_connection,
    resolve as resolve_connection,
    set_active_dataset,
)
from app.core.csv_loader import CSVUploadError, infer_schema, iter_csv, load_csv, sanitize_table_name
from app.core.dataset_loader import list_datasets, load_dataset, read_examples
from app.core.demo import DEMO_DATASET_NAME, build_demo_session, get_demo_questions
from app.core.samples import list_samples, load_sample
from app.core.session import SessionStore
from app.core.threads import (
    compact_summary_from_rows,
    get_thread_store,
    tables_from_sql,
)
from app.core.user_store import UserStore
from app.agents.coordinator import CoordinatorAgent
from app.agents.key_points import KeyPointsAgent
from app.agents.schema_linker import SchemaLinker
from app.agents.schema_agent import SchemaAgent
from app.agents.sql_agent import SQLAgent
from app.agents.viz_agent import VizAgent
from app.db.pool import PostgresPool
from app.engine.cache import QueryCache
from app.engine.schema_cache import get_schema_cache
from app.skills import get_domain_skill, list_domains, skill_guidance

load_dotenv()

QUERY_TIMEOUT_SECONDS = 180
RATE_LIMIT_QUERIES = 10       # max queries per window
RATE_LIMIT_WINDOW_SECONDS = 60  # rolling window in seconds
CLARIFY_TIMEOUT_SECONDS = 120   # wait for clarification_response before defaulting
UPLOAD_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://testuser:testpass@localhost:5432/testdb")

# Hardening knobs
ALLOW_REGISTRATION = os.getenv("ALLOW_REGISTRATION", "true").strip().lower() not in {"false", "0", "no", "off"}
AUTH_RATE_LIMIT = 5              # max account-issuing requests per IP per window
AUTH_RATE_WINDOW_SECONDS = 60
UPLOAD_MAX_BYTES = 25 * 1024 * 1024  # ~25MB CSV cap


class _UploadTooLarge(Exception):
    """Internal signal: streamed upload exceeded UPLOAD_MAX_BYTES."""


def _check_rate_limit(timestamps: deque, limit: int, window_seconds: float) -> None:
    """Raise RuntimeError if too many requests in the rolling window.

    Mutates `timestamps` — removes expired entries, then checks count.
    """
    now = time.monotonic()
    # Evict expired entries from the left
    while timestamps and now - timestamps[0] > window_seconds:
        timestamps.popleft()
    if len(timestamps) >= limit:
        raise RuntimeError(
            f"Rate limit: max {limit} requests per {window_seconds:.0f}s"
        )


session_store = SessionStore()
user_store = UserStore()  # persists to data/users.db
thread_store = get_thread_store()  # per-user conversation threads (Contract V3)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await user_store.init()
    # Demo database is registered server-side — clients only ever see its
    # opaque connection_id, never the DSN.
    await register_demo_connection()
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",          # local dev
        "https://ven-z8.github.io",       # GitHub Pages frontend
        "https://nl2sql2viz.duckdns.org", # direct backend access
    ],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


# --- Health probe ---
@app.get("/health")
async def health():
    return {"status": "ok"}


# --- REST: Register user, get API key ---
class RegisterRequest(BaseModel):
    username: str


_ip_auth_times: dict[str, deque] = {}


def _check_ip_rate_limit(request: Request) -> None:
    """Throttle account-issuing endpoints per client IP (in-memory)."""
    ip = request.client.host if request.client else "unknown"
    timestamps = _ip_auth_times.setdefault(ip, deque(maxlen=AUTH_RATE_LIMIT * 4))
    try:
        _check_rate_limit(timestamps, AUTH_RATE_LIMIT, AUTH_RATE_WINDOW_SECONDS)
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))
    timestamps.append(time.monotonic())


@app.post("/api/register")
async def register(req: RegisterRequest, request: Request):
    if not ALLOW_REGISTRATION:
        raise HTTPException(status_code=403, detail="Registration is disabled on this deployment")
    _check_ip_rate_limit(request)
    try:
        api_key = generate_api_key()
        await user_store.register(req.username, hash_api_key(api_key), key_digest(api_key))
        return {"api_key": api_key, "username": req.username}
    except ValueError:
        raise HTTPException(status_code=409, detail="Username already exists")


@app.get("/api/demo/questions")
async def demo_questions():
    return {"dataset": DEMO_DATASET_NAME, "questions": get_demo_questions()}


@app.post("/api/demo/session")
async def demo_session(request: Request):
    _check_ip_rate_limit(request)
    session = build_demo_session()
    await user_store.register(
        session["username"], hash_api_key(session["api_key"]), key_digest(session["api_key"])
    )
    # The managed demo DB is registered server-side; hand out only its id.
    session["connection_id"] = await register_demo_connection()
    return session

# --- REST: Domains + CSV upload + samples ---
@app.get("/api/domains")
async def domains():
    return {"domains": list_domains()}


@app.get("/api/samples")
async def samples_endpoint():
    return {"samples": list_samples()}


@app.get("/api/datasets")
async def datasets():
    return {"datasets": list_datasets()}


@app.post("/api/datasets/{dataset_id}/load")
async def load_dataset_endpoint(dataset_id: str, api_key: str = Form(...)):
    username = await _verify_api_key_or_raise(api_key)
    pool = PostgresPool(dsn=UPLOAD_DATABASE_URL)
    try:
        await pool.connect()
        result = await load_dataset(pool, dataset_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load dataset: {e}")
    finally:
        await pool.disconnect()
    # New tables must be visible to the very next query — drop stale schemas.
    get_schema_cache().invalidate_dsn(UPLOAD_DATABASE_URL)
    result["connection_id"] = await register_connection(UPLOAD_DATABASE_URL, owner=username)
    # Record the active dataset on the connection so the WS layer can pull
    # per-dataset few-shot examples into the SQL generation prompt.
    await set_active_dataset(result["connection_id"], dataset_id)
    return result


@app.post("/api/samples/{sample_id}/load")
async def load_sample_endpoint(sample_id: str, api_key: str = Form(...)):
    username = await _verify_api_key_or_raise(api_key)
    pool = PostgresPool(dsn=UPLOAD_DATABASE_URL)
    try:
        await pool.connect()
        result = await load_sample(pool, sample_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sample not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load sample: {e}")
    finally:
        await pool.disconnect()
    get_schema_cache().invalidate_dsn(UPLOAD_DATABASE_URL)
    result["connection_id"] = await register_connection(UPLOAD_DATABASE_URL, owner=username)
    return result


@app.post("/api/upload")
async def upload_csv(
    api_key: str = Form(...),
    domain: str = Form("general"),
    file: UploadFile = File(...),
):
    username = await _verify_api_key_or_raise(api_key)
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported")

    # Stream the upload to a temp file (memory-safe for large CSVs),
    # enforcing the size cap mid-stream so oversized uploads abort early.
    import tempfile

    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp_path = tmp.name
            received = 0
            while chunk := await file.read(1024 * 1024):
                received += len(chunk)
                if received > UPLOAD_MAX_BYTES:
                    raise _UploadTooLarge
                tmp.write(chunk)

        try:
            columns, rows = iter_csv(tmp_path)
            sample: list[dict[str, str]] = []
            for i, row in enumerate(rows):
                if i >= 1000:
                    break
                sample.append(row)
            types = infer_schema(columns, sample)
            table_name = sanitize_table_name(file.filename)
        except CSVUploadError as e:
            raise HTTPException(status_code=400, detail=str(e))

        pool = PostgresPool(dsn=UPLOAD_DATABASE_URL)
        try:
            await pool.connect()
            _, rows = iter_csv(tmp_path)
            row_count = await load_csv(pool, table_name, columns, rows, types)
        except CSVUploadError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to load CSV: {e}")
        finally:
            await pool.disconnect()

    except _UploadTooLarge:
        raise HTTPException(
            status_code=413,
            detail=f"CSV exceeds the {UPLOAD_MAX_BYTES // (1024 * 1024)} MB upload limit",
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    get_schema_cache().invalidate_dsn(UPLOAD_DATABASE_URL)
    connection_id = await register_connection(UPLOAD_DATABASE_URL, owner=username)
    return {
        "table_name": table_name,
        "row_count": row_count,
        "columns": columns,
        "types": types,
        "domain": domain,
        "preview": sample[:5],
        "connection_id": connection_id,
    }

# --- REST: Connect a database ---
class ConnectRequest(BaseModel):
    api_key: str
    dsn: str  # stored server-side only — never echoed back to any client

@app.post("/api/connections")
async def connect_db(req: ConnectRequest):
    username = await _verify_api_key_or_raise(req.api_key)
    # Test the connection before registering it
    pool = PostgresPool(dsn=req.dsn)
    try:
        await pool.connect()
        await pool.disconnect()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot connect to DB: {e}")
    connection_id = await register_connection(req.dsn, owner=username)
    # Custom-DSN: no dataset is bound to this connection, so clear any
    # stale active_dataset from a prior /api/datasets/<id>/load that
    # happened to share the DSN.
    await set_active_dataset(connection_id, "")
    return {"connection_id": connection_id}

async def _resolve_user(api_key: str) -> str | None:
    """O(1) digest lookup + single argon2 confirm; scan fallback for legacy rows."""
    username = await user_store.find_by_key_digest(key_digest(api_key))
    if username is not None:
        hashed = await user_store.get_hashed_key(username)
        return username if hashed and verify_api_key(api_key, hashed) else None
    for legacy_username, hashed in await user_store.all_users():
        if verify_api_key(api_key, hashed):
            return legacy_username
    return None


async def _verify_api_key_or_raise(api_key: str) -> str:
    username = await _resolve_user(api_key)
    if username is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return username

# --- WebSocket: NL query endpoint ---
@app.websocket("/ws/query")
async def websocket_query(websocket: WebSocket):
    await websocket.accept()

    # Step 1: Auth handshake (first message must be auth)
    try:
        auth_msg = await websocket.receive_json()
    except (WebSocketDisconnect, RuntimeError):
        return  # client left before authenticating — nothing to do
    try:
        if auth_msg.get("type") != "auth" or not auth_msg.get("api_key"):
            await websocket.close(code=4001)
            return
        user_id = await _resolve_user(auth_msg["api_key"])
        if not user_id:
            await websocket.close(code=4001)
            return

        await websocket.send_json({"type": "authenticated", "user_id": user_id})

        await session_store.create_session(user_id=user_id, connection_id=user_id)
        query_timestamps: deque = deque(maxlen=RATE_LIMIT_QUERIES)

        # Step 2: Handle queries
        while True:
            try:
                data = await websocket.receive_json()
            except (WebSocketDisconnect, RuntimeError):
                break  # client disconnected — stop this connection cleanly
            if data.get("type") != "query":
                continue

            nl_query = data.get("query", "").strip()
            connection_id = data.get("connection_id", "")
            domain = data.get("domain", "general")
            focus_table = data.get("focus_table")
            if not nl_query or not connection_id:
                await websocket.send_json({"type": "error", "message": "query and connection_id required"})
                continue

            # Rate limit check
            try:
                _check_rate_limit(query_timestamps, RATE_LIMIT_QUERIES, RATE_LIMIT_WINDOW_SECONDS)
            except RuntimeError as e:
                await websocket.send_json({"type": "error", "message": str(e)})
                continue
            query_timestamps.append(time.monotonic())

            # Resolve the connection SERVER-SIDE — clients never send DSNs,
            # and unknown/foreign connection ids are rejected identically.
            dsn = await resolve_connection(connection_id, user_id)
            if dsn is None:
                await websocket.send_json({"type": "error", "message": "unknown connection"})
                continue

            # Contract V3: conversation threads. Resolve/join the client's
            # thread (or start a fresh one) BEFORE the run so the clarify
            # channel and result events share one lifecycle. Any failure here
            # degrades to today's stateless behavior — never an error event.
            raw_thread_id = data.get("thread_id")
            supplied_thread_id = (
                raw_thread_id if isinstance(raw_thread_id, str) and raw_thread_id else None
            )
            try:
                thread = thread_store.resolve_or_create(user_id, supplied_thread_id)
            except Exception:  # noqa: BLE001 — threads must never break queries
                thread = None

            # Per-query timeout
            pool = PostgresPool(dsn=dsn)
            try:
                await pool.connect()
                query_cache = QueryCache()
                schema_agent = SchemaAgent()
                schema_agent.pool = pool
                sql_agent = SQLAgent()
                sql_agent.pool = pool
                viz_agent = VizAgent()
                linker = SchemaLinker()
                keypoints = KeyPointsAgent()
                coordinator = CoordinatorAgent()
                coordinator.schema_agent = schema_agent
                coordinator.sql_agent = sql_agent
                coordinator.viz_agent = viz_agent
                coordinator.linker = linker
                coordinator.keypoints = keypoints
                coordinator.cache = query_cache
                coordinator.connection_id = connection_id  # cache namespace per DB
                coordinator.focus_table = focus_table
                coordinator.dsn = dsn  # schema-cache key — stays server-side

                # Follow-up context: prior turns let the classifier and the
                # NL2SQL/planner prompts resolve pronouns and ellipsis.
                # Empty on fresh threads and when threads are unavailable —
                # self-contained questions behave exactly as before.
                if thread is not None:
                    try:
                        coordinator.conversation_context = thread_store.context_block(thread)
                        sql_agent.conversation_context = coordinator.conversation_context
                    except Exception:  # noqa: BLE001 — context is best-effort
                        coordinator.conversation_context = ""

                # Activate the domain skill — injects analyst guidance into SQL generation
                skill = get_domain_skill(domain)
                sql_agent.domain_guidance = skill_guidance(skill)

                # Per-dataset few-shot examples (Vanna-style RAG). Read from
                # disk on each query — cheap and lets us swap datasets
                # without restarting the WS connection.
                active_dataset = await get_active_dataset(connection_id)
                if active_dataset:
                    examples = read_examples(active_dataset)
                    sql_agent.few_shot_examples = examples
                    coordinator.few_shot_examples = examples
                else:
                    sql_agent.few_shot_examples = []
                    coordinator.few_shot_examples = []

                async def ask_user(question: str, options: list[str]) -> int | None:
                    """Clarify channel: send the question, await the choice.

                    Contract: {"type":"clarify", "question", "options",
                    "thread_id"} out; {"type":"clarification_response",
                    "choice": <int>} in. Returns None on timeout (120s),
                    disconnect, or an invalid reply so the pipeline proceeds
                    with its best-guess default. A completed round-trip is
                    recorded on the pending turn of the active thread.
                    """
                    try:
                        await websocket.send_json({
                            "type": "clarify",
                            "question": question,
                            "options": options,
                            # V3: the clarify round-trip joins the same
                            # conversation thread as its query's result.
                            "thread_id": thread.thread_id if thread is not None else user_id,
                        })
                        reply = await asyncio.wait_for(
                            websocket.receive_json(), timeout=CLARIFY_TIMEOUT_SECONDS
                        )
                    except Exception:  # noqa: BLE001 — timeout/disconnect/serialize → default path
                        return None
                    if not isinstance(reply, dict) or reply.get("type") != "clarification_response":
                        return None
                    choice = reply.get("choice")
                    if isinstance(choice, bool) or not isinstance(choice, int):
                        return None
                    if not 0 <= choice < len(options):
                        return None
                    if thread is not None:
                        try:  # record the outcome on this turn's pending slot
                            thread_store.note_clarification(thread, question, options[choice])
                        except Exception:  # noqa: BLE001
                            pass
                    return choice

                def _stamp_thread(event: dict) -> dict:
                    """Contract V3: stamp identity on result events + record the turn.

                    Adds thread_id (echoed or newly generated), turn_index
                    (1-based within the thread) and is_follow_up (client
                    supplied a thread_id → frontend morphs the chart in
                    place). Recording failures fall back to best-effort
                    values; the wire shape is always complete.
                    """
                    event = dict(event)
                    turn_index: int | None = None
                    if thread is not None:
                        try:
                            turn_index = thread_store.record_turn(
                                thread,
                                question=str(event.get("query") or nl_query),
                                sql=str(event.get("sql") or ""),
                                row_count=int(event.get("row_count") or 0),
                                summary=compact_summary_from_rows(event.get("rows") or []),
                                tables=tables_from_sql(str(event.get("sql") or "")),
                            )
                        except Exception:  # noqa: BLE001 — recording is best-effort
                            turn_index = None
                    if turn_index is None:
                        # Recording unavailable/failed — best-effort stable value.
                        turn_index = (
                            getattr(thread, "turn_counter", 0) + 1
                            if thread is not None
                            else 1
                        )
                    event["thread_id"] = (
                        thread.thread_id if thread is not None else str(uuid.uuid4())
                    )
                    event["turn_index"] = max(1, int(turn_index))
                    event["is_follow_up"] = supplied_thread_id is not None
                    return event

                async def _run_query():
                    async for event in coordinator.run(nl_query, ask_user=ask_user):
                        if isinstance(event, dict) and event.get("type") == "result":
                            event = _stamp_thread(event)
                        await websocket.send_json(event)

                try:
                    await asyncio.wait_for(_run_query(), timeout=QUERY_TIMEOUT_SECONDS)
                except asyncio.TimeoutError:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Query timed out after {QUERY_TIMEOUT_SECONDS}s",
                    })
            except WebSocketDisconnect:
                pass  # client left mid-query — nothing to send
            except Exception as e:
                try:
                    await websocket.send_json({"type": "error", "message": str(e)})
                except WebSocketDisconnect:
                    pass  # client disconnected before the error could be sent
            finally:
                # IMPORTANT: pool.disconnect() must stay here in the outer finally.
                # asyncio.wait_for cancels _run_query() but does NOT immediately call
                # aclose() on the coordinator async generator — Python schedules that
                # at GC time. Cleanup must not be moved inside coordinator.run().
                await pool.disconnect()

    except WebSocketDisconnect:
        pass
