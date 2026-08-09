# app/main.py
import asyncio
import hashlib
import os
import time
from collections import deque
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.core.auth import generate_api_key, hash_api_key, verify_api_key
from app.core.csv_loader import CSVUploadError, infer_schema, iter_csv, load_csv, sanitize_table_name
from app.core.dataset_loader import list_datasets, load_dataset
from app.core.demo import DEMO_DATASET_NAME, build_demo_session, get_demo_questions
from app.core.samples import list_samples, load_sample
from app.core.session import SessionStore
from app.core.user_store import UserStore
from app.agents.coordinator import CoordinatorAgent
from app.agents.schema_agent import SchemaAgent
from app.agents.sql_agent import SQLAgent
from app.agents.viz_agent import VizAgent
from app.db.pool import PostgresPool
from app.engine.cache import QueryCache
from app.skills import get_domain_skill, list_domains, skill_guidance

load_dotenv()

QUERY_TIMEOUT_SECONDS = 180
RATE_LIMIT_QUERIES = 10       # max queries per window
RATE_LIMIT_WINDOW_SECONDS = 60  # rolling window in seconds
UPLOAD_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://testuser:testpass@localhost:5432/testdb")


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


session_store = SessionStore()
user_store = UserStore()  # persists to data/users.db

@asynccontextmanager
async def lifespan(app: FastAPI):
    await user_store.init()
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# --- REST: Register user, get API key ---
class RegisterRequest(BaseModel):
    username: str

@app.post("/api/register")
async def register(req: RegisterRequest):
    try:
        api_key = generate_api_key()
        await user_store.register(req.username, hash_api_key(api_key))
        return {"api_key": api_key, "username": req.username}
    except ValueError:
        raise HTTPException(status_code=409, detail="Username already exists")


@app.get("/api/demo/questions")
async def demo_questions():
    return {"dataset": DEMO_DATASET_NAME, "questions": get_demo_questions()}


@app.post("/api/demo/session")
async def demo_session():
    session = build_demo_session()
    await user_store.register(session["username"], hash_api_key(session["api_key"]))
    return session

# --- REST: Domains + CSV upload + samples ---
@app.get("/api/domains")
async def domains():
    return {"domains": list_domains()}


@app.get("/api/samples")
async def samples():
    return {"samples": list_samples()}


@app.get("/api/datasets")
async def datasets():
    return {"datasets": list_datasets()}


@app.post("/api/datasets/{dataset_id}/load")
async def load_dataset_endpoint(dataset_id: str, api_key: str = Form(...)):
    await _verify_api_key_or_raise(api_key)
    pool = PostgresPool(dsn=UPLOAD_DATABASE_URL)
    try:
        await pool.connect()
        result = await load_dataset(pool, dataset_id, UPLOAD_DATABASE_URL)
    except KeyError:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load dataset: {e}")
    finally:
        await pool.disconnect()
    return result


@app.post("/api/samples/{sample_id}/load")
async def load_sample_endpoint(sample_id: str, api_key: str = Form(...)):
    await _verify_api_key_or_raise(api_key)
    pool = PostgresPool(dsn=UPLOAD_DATABASE_URL)
    try:
        await pool.connect()
        result = await load_sample(pool, sample_id, UPLOAD_DATABASE_URL)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sample not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load sample: {e}")
    finally:
        await pool.disconnect()
    return result


@app.post("/api/upload")
async def upload_csv(
    api_key: str = Form(...),
    domain: str = Form("general"),
    file: UploadFile = File(...),
):
    await _verify_api_key_or_raise(api_key)
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported")

    # Stream the upload to a temp file (memory-safe for large CSVs)
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp_path = tmp.name
        while chunk := await file.read(1024 * 1024):
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
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return {
        "table_name": table_name,
        "row_count": row_count,
        "columns": columns,
        "types": types,
        "domain": domain,
        "preview": sample[:5],
        "dsn": UPLOAD_DATABASE_URL,
    }

# --- REST: Connect a database ---
class ConnectRequest(BaseModel):
    api_key: str
    dsn: str  # Phase 1: plain DSN. Phase 2: encrypted via security.py

@app.post("/api/connections")
async def connect_db(req: ConnectRequest):
    await _verify_api_key_or_raise(req.api_key)
    # Test the connection
    pool = PostgresPool(dsn=req.dsn)
    try:
        await pool.connect()
        await pool.disconnect()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot connect to DB: {e}")
    connection_id = hashlib.sha256(req.dsn.encode()).hexdigest()[:16]  # deterministic
    return {"connection_id": connection_id}

async def _verify_api_key_or_raise(api_key: str) -> str:
    for username, hashed in await user_store.all_users():
        if verify_api_key(api_key, hashed):
            return username
    raise HTTPException(status_code=401, detail="Invalid API key")

# --- WebSocket: NL query endpoint ---
@app.websocket("/ws/query")
async def websocket_query(websocket: WebSocket):
    await websocket.accept()

    # Step 1: Auth handshake (first message must be auth)
    try:
        auth_msg = await websocket.receive_json()
        if auth_msg.get("type") != "auth" or not auth_msg.get("api_key"):
            await websocket.close(code=4001)
            return
        user_id = None
        for username, hashed in await user_store.all_users():
            if verify_api_key(auth_msg["api_key"], hashed):
                user_id = username
                break
        if not user_id:
            await websocket.close(code=4001)
            return

        await websocket.send_json({"type": "authenticated", "user_id": user_id})

        await session_store.create_session(user_id=user_id, connection_id=user_id)
        query_timestamps: deque = deque(maxlen=RATE_LIMIT_QUERIES)

        # Step 2: Handle queries
        while True:
            data = await websocket.receive_json()
            if data.get("type") != "query":
                continue

            nl_query = data.get("query", "").strip()
            dsn = data.get("dsn", "")
            domain = data.get("domain", "general")
            focus_table = data.get("focus_table")
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
            pool = PostgresPool(dsn=dsn)
            try:
                await pool.connect()
                query_cache = QueryCache()
                schema_agent = SchemaAgent()
                schema_agent.pool = pool
                sql_agent = SQLAgent()
                sql_agent.pool = pool
                viz_agent = VizAgent()
                coordinator = CoordinatorAgent()
                coordinator.schema_agent = schema_agent
                coordinator.sql_agent = sql_agent
                coordinator.viz_agent = viz_agent
                coordinator.cache = query_cache
                coordinator.connection_id = user_id or "default"
                coordinator.focus_table = focus_table
                # Activate the domain skill — injects analyst guidance into SQL generation
                skill = get_domain_skill(domain)
                sql_agent.domain_guidance = skill_guidance(skill)

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
                # IMPORTANT: pool.disconnect() must stay here in the outer finally.
                # asyncio.wait_for cancels _run_query() but does NOT immediately call
                # aclose() on the coordinator async generator — Python schedules that
                # at GC time. Cleanup must not be moved inside coordinator.run().
                await pool.disconnect()

    except WebSocketDisconnect:
        pass
