import sqlite3  # for sqlite3.IntegrityError — aiosqlite re-raises stdlib exceptions

import aiosqlite
from pathlib import Path
from typing import Optional

# Compute absolute default path relative to this file's location:
# app/core/user_store.py → project root is two levels up → data/users.db
_DEFAULT_DB_PATH = str(Path(__file__).parent.parent.parent / "data" / "users.db")


class UserStore:
    """Persistent user store backed by SQLite.

    Args:
        db_path: Path to SQLite file. Default: "data/users.db".
                 For testing, use a temp file (e.g. pytest's tmp_path / "test.db").
                 Do NOT use ":memory:" — each aiosqlite.connect() call opens
                 a separate in-process database, so the table created by init()
                 would be invisible to all subsequent method calls.
    """

    def __init__(self, db_path: str = _DEFAULT_DB_PATH) -> None:
        self._db_path = db_path

    async def init(self) -> None:
        """Create the users table if it doesn't exist."""
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
