import pytest

from app.db.pool import PostgresPool


@pytest.mark.asyncio
async def test_connect_and_disconnect(postgres_dsn):
    pool = PostgresPool(dsn=postgres_dsn)
    await pool.connect()
    assert pool.is_connected
    await pool.disconnect()
    assert not pool.is_connected


@pytest.mark.asyncio
async def test_execute_returns_rows(postgres_dsn):
    pool = PostgresPool(dsn=postgres_dsn)
    await pool.connect()
    result = await pool.execute("SELECT 1 AS num")
    await pool.disconnect()
    assert result.rows == [{"num": 1}]
    assert result.row_count == 1


@pytest.mark.asyncio
async def test_write_query_is_rejected(postgres_dsn):
    pool = PostgresPool(dsn=postgres_dsn)
    await pool.connect()
    with pytest.raises(ValueError, match="read-only"):
        await pool.execute("INSERT INTO pg_class VALUES (1)")
    await pool.disconnect()


@pytest.mark.asyncio
async def test_get_schema_returns_tables(postgres_dsn):
    pool = PostgresPool(dsn=postgres_dsn)
    await pool.connect()
    schema = await pool.get_schema()
    await pool.disconnect()
    assert "test_users" in schema.tables  # seeded by conftest
