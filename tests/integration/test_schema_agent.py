import pytest
from app.agents.schema_agent import SchemaAgent
from app.connectors.postgres import PostgresConnector


@pytest.mark.asyncio
async def test_schema_agent_returns_compact_map(postgres_dsn):
    connector = PostgresConnector(dsn=postgres_dsn)
    await connector.connect()
    agent = SchemaAgent(connector=connector)
    schema_map = await agent.get_schema_map()
    await connector.disconnect()
    assert isinstance(schema_map, str)
    assert len(schema_map) > 10  # non-empty compact representation


@pytest.mark.asyncio
async def test_schema_agent_uses_cache(postgres_dsn):
    from app.core.session import SessionStore
    store = SessionStore()
    session_id = await store.create_session("u1", "c1")
    connector = PostgresConnector(dsn=postgres_dsn)
    await connector.connect()
    agent = SchemaAgent(connector=connector, session_store=store, session_id=session_id)

    # First call hits DB
    map1 = await agent.get_schema_map()
    # Second call should use cache (connector is closed)
    await connector.disconnect()
    map2 = await agent.get_schema_map()
    assert map1 == map2
