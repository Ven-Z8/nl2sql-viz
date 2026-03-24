import pytest
import json
from unittest.mock import patch, MagicMock
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


def test_viz_agent_returns_valid_vega_spec():
    agent = VizAgent()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=MOCK_VEGA_SPEC)]

    with patch("app.agents.viz_agent._client.messages.create", return_value=mock_response):
        import asyncio
        spec = asyncio.run(agent.run(
            nl_query="Total sales by region",
            rows=SAMPLE_ROWS,
        ))

    parsed = json.loads(spec)
    assert "$schema" in parsed
    assert "mark" in parsed
    assert "data" in parsed
    assert "encoding" in parsed


def test_viz_agent_raises_on_invalid_json():
    agent = VizAgent()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="not valid json {{{")]

    with patch("app.agents.viz_agent._client.messages.create", return_value=mock_response):
        import asyncio
        with pytest.raises(ValueError, match="Invalid Vega-Lite JSON"):
            asyncio.run(agent.run(nl_query="test", rows=[]))
