import pytest
import pytest_asyncio
from app.core.user_store import UserStore


@pytest_asyncio.fixture  # Required for pytest-asyncio >= 0.21 (project uses 1.x)
async def store(tmp_path):
    """File-based SQLite store via pytest's tmp_path (auto-cleaned after each test).

    IMPORTANT: UserStore opens a new aiosqlite.connect() per operation.
    With ":memory:", each call gets a separate empty database — the table
    created by init() would disappear immediately. Use a real temp file instead.
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
