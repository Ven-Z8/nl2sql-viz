import pytest

from app.agents.schema_agent import SchemaAgent
from app.db.pool import PostgresPool


@pytest.mark.asyncio
async def test_schema_agent_returns_compact_map(postgres_dsn):
    pool = PostgresPool(dsn=postgres_dsn)
    await pool.connect()
    agent = SchemaAgent()
    agent.pool = pool
    schema = await agent.fetch_schema()
    await pool.disconnect()
    text = schema.compact_repr()
    assert len(text) > 10  # non-empty compact representation


@pytest.mark.asyncio
async def test_schema_agent_uses_cache(postgres_dsn):
    pool = PostgresPool(dsn=postgres_dsn)
    await pool.connect()
    agent = SchemaAgent()
    agent.pool = pool

    # First call hits DB
    schema1 = await agent.fetch_schema()
    # Second call should use cache (pool is disconnected)
    await pool.disconnect()
    schema2 = await agent.fetch_schema()
    assert schema1 == schema2
