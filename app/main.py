# app/main.py
import asyncio
import hashlib
import time
from collections import deque
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.core.auth import generate_api_key, hash_api_key, verify_api_key
from app.core.session import SessionStore
from app.core.user_store import UserStore
from app.connectors.postgres import PostgresConnector
from app.agents.coordinator import Coordinator

load_dotenv()

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

# --- REST: Connect a database ---
class ConnectRequest(BaseModel):
    api_key: str
    dsn: str  # Phase 1: plain DSN. Phase 2: encrypted via security.py

@app.post("/api/connections")
async def connect_db(req: ConnectRequest):
    await _verify_api_key_or_raise(req.api_key)
    # Test the connection
    conn = PostgresConnector(dsn=req.dsn)
    try:
        await conn.connect()
        await conn.disconnect()
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

        session_id = await session_store.create_session(
            user_id=user_id, connection_id=user_id
        )
        query_timestamps: deque = deque()

        # Step 2: Handle queries
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
                # IMPORTANT: connector.disconnect() must stay here in the outer finally.
                # asyncio.wait_for cancels _run_query() but does NOT immediately call
                # aclose() on the coordinator async generator — Python schedules that
                # at GC time. Cleanup must not be moved inside coordinator.run().
                await connector.disconnect()

    except WebSocketDisconnect:
        pass
