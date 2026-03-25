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
