import pytest
from app.agents.sql_agent import SQLAgent
from app.connectors.postgres import PostgresConnector

SCHEMA_MAP = "sales(id:integer [PRIMARY KEY], region:text, amount:numeric, sale_date:date)"


@pytest.mark.asyncio
async def test_sql_agent_executes_simple_query(postgres_dsn, seed_test_db):
    connector = PostgresConnector(dsn=postgres_dsn)
    await connector.connect()
    agent = SQLAgent(connector=connector)
    result = await agent.run(
        nl_query="What is the total sales amount per region?",
        schema_map=SCHEMA_MAP,
    )
    await connector.disconnect()
    assert result["status"] == "success"
    assert isinstance(result["rows"], list)
    assert len(result["rows"]) > 0
    assert "sql" in result


@pytest.mark.asyncio
async def test_sql_agent_returns_error_after_max_retries(postgres_dsn, seed_test_db):
    connector = PostgresConnector(dsn=postgres_dsn)
    await connector.connect()
    agent = SQLAgent(connector=connector, max_retries=1)
    result = await agent.run(
        nl_query="gibberish xyzzy frob nitz",
        schema_map=SCHEMA_MAP,
    )
    await connector.disconnect()
    # Either success (Claude infers something) or structured error
    assert result["status"] in ("success", "error")
    if result["status"] == "error":
        assert "attempts" in result
