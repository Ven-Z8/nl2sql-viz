import pytest
from app.core.session import SessionStore


@pytest.mark.asyncio
async def test_create_and_get_session():
    store = SessionStore()
    session_id = await store.create_session(user_id="user1", connection_id="conn1")
    session = await store.get_session(session_id)
    assert session is not None
    assert session["user_id"] == "user1"


@pytest.mark.asyncio
async def test_set_and_get_schema_cache():
    store = SessionStore()
    session_id = await store.create_session(user_id="u1", connection_id="c1")
    schema = {"tables": ["orders", "users"]}
    await store.set_schema_cache(session_id, schema)
    cached = await store.get_schema_cache(session_id)
    assert cached == schema


@pytest.mark.asyncio
async def test_schema_cache_returns_none_after_invalidation():
    store = SessionStore()
    session_id = await store.create_session(user_id="u1", connection_id="c1")
    await store.set_schema_cache(session_id, {"tables": []})
    await store.invalidate_schema_cache(session_id)
    assert await store.get_schema_cache(session_id) is None
