import pytest

from app.agents.sql_agent import SQLAgent
from app.db.pool import PostgresPool
from app.models import ColumnInfo, SchemaMap

SCHEMA = SchemaMap(
    tables=["sales"],
    columns={"sales": [
        ColumnInfo(column="id", type="integer", constraint="PRIMARY KEY"),
        ColumnInfo(column="region", type="text"),
        ColumnInfo(column="amount", type="numeric"),
        ColumnInfo(column="sale_date", type="date"),
    ]},
    row_estimates={"sales": 4},
)


@pytest.mark.asyncio
async def test_sql_agent_generates_and_executes_simple_query(postgres_dsn, seed_test_db):
    """SQLAgent generates SQL via NOOA CodeAct and executes it against Postgres."""
    pool = PostgresPool(dsn=postgres_dsn)
    await pool.connect()
    agent = SQLAgent()
    agent.pool = pool

    generated = await agent.generate_simple(
        question="What is the total sales amount per region?",
        schema=SCHEMA,
    )
    result = await agent.execute_query(generated.sql)
    await pool.disconnect()

    assert result.row_count > 0
    assert "region" in result.columns


@pytest.mark.asyncio
async def test_sql_agent_rejects_mutating_generated_sql(postgres_dsn):
    """validate_sql helper rejects non-read-only SQL."""
    pool = PostgresPool(dsn=postgres_dsn)
    await pool.connect()
    agent = SQLAgent()
    agent.pool = pool
    await pool.disconnect()

    assert agent.validate_sql("SELECT region FROM sales") == "OK"
    assert "read-only" in agent.validate_sql("DROP TABLE sales")
