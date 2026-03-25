import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.execution.bun_sandbox import BunSandbox, BunSandboxError, BunTimeoutError


def test_bun_sandbox_error_is_exception():
    err = BunSandboxError("test")
    assert isinstance(err, Exception)


def test_bun_timeout_error_is_sandbox_error():
    err = BunTimeoutError("timeout")
    assert isinstance(err, BunSandboxError)


@pytest.mark.asyncio
async def test_run_returns_transformed_rows():
    sandbox = BunSandbox()
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    stdout_data = json.dumps([{"doubled": 2}]).encode()
    mock_proc.communicate = AsyncMock(return_value=(stdout_data, b""))

    with patch("app.execution.bun_sandbox.asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await sandbox.run(
            code="const result = rows.map(r => ({doubled: r.val * 2}));",
            input_data=[{"val": 1}],
        )
    assert result == [{"doubled": 2}]


@pytest.mark.asyncio
async def test_run_raises_on_nonzero_exit():
    sandbox = BunSandbox()
    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.communicate = AsyncMock(return_value=(b"", b"ReferenceError: result is not defined"))

    with patch("app.execution.bun_sandbox.asyncio.create_subprocess_exec", return_value=mock_proc):
        with pytest.raises(BunSandboxError, match="result is not defined"):
            await sandbox.run(code="// forgot to define result", input_data=[])


@pytest.mark.asyncio
async def test_run_raises_on_timeout():
    sandbox = BunSandbox(timeout=1)

    async def slow_communicate(*args, **kwargs):
        await asyncio.sleep(10)
        return b"", b""

    mock_proc = MagicMock()
    mock_proc.kill = MagicMock()
    mock_proc.wait = AsyncMock(return_value=None)
    mock_proc.communicate = slow_communicate

    with patch("app.execution.bun_sandbox.asyncio.create_subprocess_exec", return_value=mock_proc):
        with pytest.raises(BunTimeoutError):
            await sandbox.run(code="while(true){}", input_data=[])

    mock_proc.kill.assert_called_once()
    mock_proc.wait.assert_called_once()


@pytest.mark.asyncio
async def test_run_raises_on_invalid_json_output():
    sandbox = BunSandbox()
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"not json!!!", b""))

    with patch("app.execution.bun_sandbox.asyncio.create_subprocess_exec", return_value=mock_proc):
        with pytest.raises(BunSandboxError, match="not valid JSON"):
            await sandbox.run(code="const result = 'oops'", input_data=[])
