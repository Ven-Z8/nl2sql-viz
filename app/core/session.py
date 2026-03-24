import time
import uuid
from typing import Any, Optional

SCHEMA_CACHE_TTL_SECONDS = 600  # 10 minutes


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}
        self._schema_cache: dict[str, dict[str, Any]] = {}  # session_id -> {schema, expires_at}

    async def create_session(self, user_id: str, connection_id: str) -> str:
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = {
            "user_id": user_id,
            "connection_id": connection_id,
            "created_at": time.time(),
        }
        return session_id

    async def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        return self._sessions.get(session_id)

    async def set_schema_cache(self, session_id: str, schema: Any) -> None:
        self._schema_cache[session_id] = {
            "schema": schema,
            "expires_at": time.time() + SCHEMA_CACHE_TTL_SECONDS,
        }

    async def get_schema_cache(self, session_id: str) -> Optional[Any]:
        entry = self._schema_cache.get(session_id)
        if entry is None:
            return None
        if time.time() > entry["expires_at"]:
            del self._schema_cache[session_id]
            return None
        return entry["schema"]

    async def invalidate_schema_cache(self, session_id: str) -> None:
        self._schema_cache.pop(session_id, None)
