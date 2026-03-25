import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from app.agents.viz_agent import VizAgent

SAMPLE_ROWS = [
    {"region": "North", "total": 2500.00},
    {"region": "South", "total": 2000.00},
    {"region": "East", "total": 800.00},
]

MOCK_VEGA_SPEC = json.dumps({
    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
    "mark": "bar",
    "data": {"values": SAMPLE_ROWS},
    "encoding": {
        "x": {"field": "region", "type": "nominal"},
        "y": {"field": "total", "type": "quantitative"}
    }
})


@pytest.mark.asyncio
async def test_viz_agent_uses_async_client():
    from anthropic import AsyncAnthropic
    agent = VizAgent()
    assert isinstance(agent._client, AsyncAnthropic)


@pytest.mark.asyncio
async def test_viz_agent_returns_valid_vega_spec():
    agent = VizAgent()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=MOCK_VEGA_SPEC)]

    agent._client = AsyncMock()
    agent._client.messages.create = AsyncMock(return_value=mock_response)

    spec = await agent.run(nl_query="Total sales by region", rows=SAMPLE_ROWS)

    parsed = json.loads(spec)
    assert "$schema" in parsed
    assert "mark" in parsed
    assert "data" in parsed
    assert "encoding" in parsed


@pytest.mark.asyncio
async def test_viz_agent_raises_on_invalid_json():
    agent = VizAgent()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="not valid json {{{")]

    agent._client = AsyncMock()
    agent._client.messages.create = AsyncMock(return_value=mock_response)

    with pytest.raises(ValueError, match="Invalid Vega-Lite JSON"):
        await agent.run(nl_query="test", rows=[])
