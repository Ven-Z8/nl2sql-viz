import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.agents.code_exec_agent import CodeExecAgent
from app.execution.bun_sandbox import BunSandboxError, BunTimeoutError


def _make_claude_response(text: str) -> MagicMock:
    content = MagicMock()
    content.text = text
    resp = MagicMock()
    resp.content = [content]
    return resp


@pytest.mark.asyncio
async def test_run_returns_transformed_rows():
    mock_sandbox = MagicMock()
    mock_sandbox.run = AsyncMock(return_value=[{"region": "North", "pct": 0.6}])

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(
        return_value=_make_claude_response(
            "const result = rows.map(r => ({...r, pct: r.amount / 1000}));"
        )
    )

    # Patch Anthropic class BEFORE construction so __init__ gets the mock
    with patch("app.agents.code_exec_agent.AsyncAnthropic", return_value=mock_client):
        agent = CodeExecAgent(sandbox=mock_sandbox)
        result = await agent.run(
            nl_query="What percentage does each region contribute?",
            rows=[{"region": "North", "amount": 600}, {"region": "South", "amount": 400}],
            schema_map="sales(region:text, amount:numeric)",
        )

    assert result["status"] == "success"
    assert result["rows"] == [{"region": "North", "pct": 0.6}]
    assert "code" in result


@pytest.mark.asyncio
async def test_run_strips_markdown_fences():
    """Claude sometimes wraps code in ```javascript ... ``` fences."""
    mock_sandbox = MagicMock()
    mock_sandbox.run = AsyncMock(return_value=[{"x": 1}])

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(
        return_value=_make_claude_response(
            "```javascript\nconst result = rows;\n```"
        )
    )

    with patch("app.agents.code_exec_agent.AsyncAnthropic", return_value=mock_client):
        agent = CodeExecAgent(sandbox=mock_sandbox)
        result = await agent.run("test", [{"x": 1}], "schema")

    assert result["status"] == "success"
    # Verify the code passed to sandbox has no fences
    passed_code = mock_sandbox.run.call_args.kwargs["code"]
    assert "```" not in passed_code
    assert "const result = rows;" in passed_code


@pytest.mark.asyncio
async def test_run_returns_timeout_on_bun_timeout():
    mock_sandbox = MagicMock()
    mock_sandbox.run = AsyncMock(side_effect=BunTimeoutError("timed out"))

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(
        return_value=_make_claude_response("const result = rows;")
    )

    with patch("app.agents.code_exec_agent.AsyncAnthropic", return_value=mock_client):
        agent = CodeExecAgent(sandbox=mock_sandbox)
        result = await agent.run("test", [{"x": 1}], "schema")

    assert result["status"] == "timeout"
    assert "timed out" in result["message"].lower() or "timeout" in result["message"].lower()


@pytest.mark.asyncio
async def test_run_returns_error_on_sandbox_error():
    mock_sandbox = MagicMock()
    mock_sandbox.run = AsyncMock(side_effect=BunSandboxError("ReferenceError: result not defined"))

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(
        return_value=_make_claude_response("// no result defined")
    )

    with patch("app.agents.code_exec_agent.AsyncAnthropic", return_value=mock_client):
        agent = CodeExecAgent(sandbox=mock_sandbox)
        result = await agent.run("test", [{"x": 1}], "schema")

    assert result["status"] == "error"
    assert "result" in result["message"].lower() or "ReferenceError" in result["message"]
