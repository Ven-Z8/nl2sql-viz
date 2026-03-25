import pytest
from unittest.mock import AsyncMock, MagicMock
from app.agents.sql_agent import SQLAgent


@pytest.mark.asyncio
async def test_sql_agent_uses_async_client():
    """SQLAgent must use AsyncAnthropic (not sync Anthropic)."""
    from anthropic import AsyncAnthropic
    agent = SQLAgent(connector=MagicMock())
    assert isinstance(agent._client, AsyncAnthropic), (
        "SQLAgent._client must be AsyncAnthropic, not Anthropic"
    )


@pytest.mark.asyncio
async def test_sql_agent_returns_sql_on_success():
    """SQLAgent.run() returns status=success with sql and rows."""
    mock_connector = AsyncMock()
    mock_connector.execute_read = AsyncMock(return_value=[{"count": 3}])

    agent = SQLAgent(connector=mock_connector)
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="SELECT COUNT(*) FROM sales")]
    agent._client = AsyncMock()
    agent._client.messages.create = AsyncMock(return_value=mock_response)

    result = await agent.run(nl_query="How many sales?", schema_map="sales(id, amount)")
    assert result["status"] == "success"
    assert "SELECT" in result["sql"]
    assert result["rows"] == [{"count": 3}]


@pytest.mark.asyncio
async def test_sql_agent_retries_on_connector_error():
    """SQLAgent retries up to max_retries times when execute_read raises."""
    mock_connector = AsyncMock()
    # Fail on attempt 1, succeed on attempt 2
    mock_connector.execute_read = AsyncMock(
        side_effect=[Exception("syntax error"), [{"id": 1}]]
    )

    agent = SQLAgent(connector=mock_connector, max_retries=3)
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="SELECT id FROM sales")]
    agent._client = AsyncMock()
    agent._client.messages.create = AsyncMock(return_value=mock_response)

    result = await agent.run(nl_query="Get all IDs", schema_map="sales(id)")
    assert result["status"] == "success"
    assert result["attempts"] == 2
    assert mock_connector.execute_read.call_count == 2


@pytest.mark.asyncio
async def test_sql_agent_returns_error_after_max_retries():
    """SQLAgent returns status=error after exhausting all retries."""
    mock_connector = AsyncMock()
    mock_connector.execute_read = AsyncMock(side_effect=Exception("always fails"))

    agent = SQLAgent(connector=mock_connector, max_retries=3)
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="SELECT bad FROM nowhere")]
    agent._client = AsyncMock()
    agent._client.messages.create = AsyncMock(return_value=mock_response)

    result = await agent.run(nl_query="Bad query", schema_map="sales(id)")
    assert result["status"] == "error"
    assert result["attempts"] == 3
    assert "always fails" in result["last_error"]
    assert mock_connector.execute_read.call_count == 3
