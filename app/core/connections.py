"""Server-side connection registry — maps connection_id → Postgres DSN.

Security model: clients never receive DSNs. They hold opaque connection_ids
(deterministic sha256[:16] of the DSN) and the server resolves them here.
The demo database is registered at startup as a shared connection (no owner);
users register their own DSNs via POST /api/connections and only they
(or shared/demo entries) may use them.

NOTE: this registry is IN-MEMORY ONLY — registered connections do not
survive a process restart. The demo connection is re-registered in the app
lifespan, and users simply re-POST /api/connections after a restart.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from dataclasses import dataclass, field

DEFAULT_DEMO_DSN = "postgresql://testuser:testpass@localhost:5432/testdb"


def get_demo_dsn() -> str:
    """Return the configured demo DSN (DEMO_DATABASE_URL or DATABASE_URL)."""
    return os.getenv("DEMO_DATABASE_URL") or os.getenv("DATABASE_URL") or DEFAULT_DEMO_DSN


def connection_id_for_dsn(dsn: str) -> str:
    """Deterministic public identifier for a DSN (stable across restarts)."""
    return hashlib.sha256(dsn.encode()).hexdigest()[:16]


@dataclass
class ConnectionEntry:
    """One registered database connection.

    ``owners`` holds usernames allowed to use this connection. A ``None``
    member means the connection is SHARED (the demo database) — any
    authenticated user may query it. ``active_dataset`` records the most
    recently loaded dataset id (e.g. via /api/datasets/<id>/load) so the
    WebSocket layer can pull per-dataset few-shot examples without
    re-asking the client.
    """

    dsn: str
    owners: set[str | None] = field(default_factory=set)
    active_dataset: str | None = None


_registry: dict[str, ConnectionEntry] = {}
_lock = asyncio.Lock()


async def register(dsn: str, owner: str | None = None) -> str:
    """Register a DSN under its deterministic id. Returns the connection_id.

    Re-registering an existing id adds the owner to the allowed set instead
    of replacing it, so two users who point at the same database both keep
    access while neither learns the other's credentials.
    """
    cid = connection_id_for_dsn(dsn)
    async with _lock:
        entry = _registry.get(cid)
        if entry is None:
            _registry[cid] = ConnectionEntry(dsn=dsn, owners={owner})
        else:
            entry.owners.add(owner)
    return cid


async def set_active_dataset(connection_id: str, dataset_id: str) -> None:
    """Record the dataset most recently loaded onto a connection.

    The WebSocket layer reads this to attach per-dataset few-shot examples
    to the SQL generation prompt. No-op if the connection is unknown.
    """
    async with _lock:
        entry = _registry.get(connection_id)
        if entry is not None:
            entry.active_dataset = dataset_id


async def get_active_dataset(connection_id: str) -> str | None:
    """Return the dataset id most recently loaded onto a connection, or None.

    Treats an empty string the same as None so a custom-DSN connection
    (which we explicitly clear to "") doesn't accidentally pull examples
    for a previously-loaded dataset.
    """
    async with _lock:
        entry = _registry.get(connection_id)
        if entry is None or not entry.active_dataset:
            return None
        return entry.active_dataset


async def register_demo_connection() -> str:
    """Register the managed demo database as a shared connection."""
    return await register(get_demo_dsn(), owner=None)


async def resolve(connection_id: str, username: str | None) -> str | None:
    """Resolve a connection_id to its DSN for an authenticated user.

    Returns None for unknown ids AND for foreign ids (a connection owned by
    another user) — callers send the same "unknown connection" error either
    way, so ownership leaks nothing.
    """
    async with _lock:
        entry = _registry.get(connection_id)
        if entry is None:
            return None
        if None not in entry.owners and username not in entry.owners:
            return None
        return entry.dsn


async def reset_registry() -> None:
    """Test helper — clear all registrations."""
    async with _lock:
        _registry.clear()
