import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

# Production hardening (not active in dev):
# Wrap the bun command in:
#   docker run --rm --network=none --read-only --tmpfs /tmp:size=64m
#            --memory=512m --cpus=1 oven/bun:alpine bun run /tmp/script.js
# The interface here is identical — only the command list changes.

BUN_TIMEOUT_SECONDS = 30

_JS_WRAPPER_HEADER = """\
const input = JSON.parse(await Bun.stdin.text());
const rows = input.rows;
// --- USER CODE ---
"""

_JS_WRAPPER_FOOTER = """\
// --- END USER CODE ---
process.stdout.write(JSON.stringify(result));
"""


class BunSandboxError(Exception):
    """Raised when BUN subprocess fails or produces invalid output."""


class BunTimeoutError(BunSandboxError):
    """Raised when BUN subprocess exceeds the wall-clock timeout."""


class BunSandbox:
    """Runs JavaScript code in a BUN subprocess with stdin/stdout JSON protocol.

    Input: rows (list of dicts) passed as stdin JSON.
    Output: result (list of dicts) read from stdout JSON.
    User code receives `rows` and must define `result`.
    """

    def __init__(self, timeout: int = BUN_TIMEOUT_SECONDS) -> None:
        self._timeout = timeout
        self._bun_path = shutil.which("bun") or "bun"

    async def run(
        self, code: str, input_data: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Execute JS code with input_data as stdin, return parsed stdout.

        Args:
            code: JavaScript code. Must define a `result` variable (array of objects).
            input_data: Rows to transform, passed as {"rows": [...]} via stdin.

        Returns:
            The transformed rows parsed from stdout JSON.

        Raises:
            BunTimeoutError: If execution exceeds self._timeout seconds.
            BunSandboxError: If process exits non-zero or stdout is not valid JSON.
        """
        script_content = _JS_WRAPPER_HEADER + code + "\n" + _JS_WRAPPER_FOOTER
        stdin_payload = json.dumps({"rows": input_data}).encode()

        with tempfile.NamedTemporaryFile(
            suffix=".js", mode="w", delete=False
        ) as tmp:
            tmp.write(script_content)
            tmp_path = tmp.name

        try:
            proc = await asyncio.create_subprocess_exec(
                self._bun_path,
                "run",
                tmp_path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(input=stdin_payload),
                    timeout=self._timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                raise BunTimeoutError(
                    f"BUN execution timed out after {self._timeout}s"
                )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        if proc.returncode != 0:
            raise BunSandboxError(
                f"BUN process exited {proc.returncode}: {stderr.decode()[:500]}"
            )

        try:
            parsed = json.loads(stdout.decode())
            if not isinstance(parsed, list):
                raise BunSandboxError(
                    f"BUN output must be a JSON array, got {type(parsed).__name__}"
                )
            return parsed
        except json.JSONDecodeError as exc:
            raise BunSandboxError(
                f"BUN output was not valid JSON: {exc}"
            ) from exc
