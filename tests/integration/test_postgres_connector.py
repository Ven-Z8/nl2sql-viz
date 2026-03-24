import pytest
from app.connectors.postgres import PostgresConnector


@pytest.mark.asyncio
async def test_connect_and_disconnect(postgres_dsn):
    conn = PostgresConnector(dsn=postgres_dsn)
    await conn.connect()
    await conn.disconnect()


@pytest.mark.asyncio
async def test_execute_read_returns_rows(postgres_dsn):
    conn = PostgresConnector(dsn=postgres_dsn)
    await conn.connect()
    rows = await conn.execute_read("SELECT 1 AS num")
    await conn.disconnect()
    assert rows == [{"num": 1}]


@pytest.mark.asyncio
async def test_write_query_is_rejected(postgres_dsn):
    conn = PostgresConnector(dsn=postgres_dsn)
    await conn.connect()
    with pytest.raises(Exception, match="read-only"):
        await conn.execute_read("INSERT INTO pg_class VALUES (1)")
    await conn.disconnect()


@pytest.mark.asyncio
async def test_get_schema_returns_tables(postgres_dsn):
    conn = PostgresConnector(dsn=postgres_dsn)
    await conn.connect()
    schema = await conn.get_schema()
    await conn.disconnect()
    assert "tables" in schema
    assert isinstance(schema["tables"], list)
