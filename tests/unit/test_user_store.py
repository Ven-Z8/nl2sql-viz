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


@pytest.mark.asyncio
async def test_find_by_key_digest(store):
    await store.register("erin", "hash_e", key_digest="digest_e")
    await store.register("frank", "hash_f")  # legacy row, no digest
    assert await store.find_by_key_digest("digest_e") == "erin"
    assert await store.find_by_key_digest("digest_missing") is None


@pytest.mark.asyncio
async def test_init_migrates_pre_digest_db(tmp_path):
    """A database created before the key_digest column must keep working."""
    import aiosqlite

    db_path = str(tmp_path / "legacy_users.db")
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "CREATE TABLE users (username TEXT PRIMARY KEY, hashed_key TEXT NOT NULL)"
        )
        await db.execute(
            "INSERT INTO users (username, hashed_key) VALUES ('ghost', 'hash_g')"
        )
        await db.commit()

    store = UserStore(db_path=db_path)
    await store.init()
    assert await store.exists("ghost") is True
    # Legacy rows have no digest; new rows register with one on the migrated table.
    await store.register("new", "hash_n", key_digest="digest_n")
    assert await store.find_by_key_digest("digest_n") == "new"
    assert await store.find_by_key_digest("digest_ghost") is None
