import json
import re
from typing import Any

from anthropic import Anthropic

from app.execution.bun_sandbox import BunSandbox, BunSandboxError, BunTimeoutError

_CODE_EXEC_SYSTEM = """\
You are a JavaScript data transformation expert working with BUN runtime.

You receive database rows and write JavaScript to transform them for a user's query.

Rules (critical — violations cause a crash):
- `rows` is already defined as an array of objects (do NOT redeclare it)
- You MUST set `result` to an array of objects (the transformed output)
- Do NOT use: fetch(), XMLHttpRequest, require(), import(), Bun.file(), fs, child_process
- Do NOT access: process.env, Bun.env, globalThis
- Pure data transformation only — no I/O, no network, no filesystem

Return ONLY the JavaScript code — no markdown, no explanation, no backticks."""


class CodeExecAgent:
    """Generates and runs a JavaScript transformation via BUN sandbox.

    Claude generates the JS code; BunSandbox executes it.
    """

    def __init__(self, sandbox: BunSandbox | None = None) -> None:
        self._client = Anthropic()
        self._sandbox = sandbox or BunSandbox()

    async def run(
        self,
        nl_query: str,
        rows: list[dict[str, Any]],
        schema_map: str,
    ) -> dict[str, Any]:
        """Generate and run a JS transformation for the given rows.

        Args:
            nl_query: The user's natural language question.
            rows: All result rows from SQL Agent.
            schema_map: Compact schema string from Schema Agent.

        Returns:
            {"status": "success", "rows": [...], "code": "..."}
            {"status": "timeout", "message": "..."}
            {"status": "error", "message": "..."}
        """
        sample = rows[:10]
        prompt = (
            f"Transform this data to fully answer the user's question.\n\n"
            f"Question: {nl_query}\n\n"
            f"Schema:\n{schema_map}\n\n"
            f"Input rows (first {len(sample)} of {len(rows)} total):\n"
            f"{json.dumps(sample, indent=2)}\n\n"
            f"Write JavaScript that transforms the full `rows` array and sets `result`."
        )

        response = self._client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=_CODE_EXEC_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )

        code = response.content[0].text.strip()
        # Strip markdown fences (```javascript ... ``` or ``` ... ```)
        code = re.sub(r"^```[a-z]*\s*", "", code, flags=re.IGNORECASE)
        code = re.sub(r"\s*```$", "", code).strip()

        try:
            result_rows = await self._sandbox.run(code=code, input_data=rows)
            return {"status": "success", "rows": result_rows, "code": code}
        except BunTimeoutError as exc:
            return {"status": "timeout", "message": str(exc)}
        except BunSandboxError as exc:
            return {"status": "error", "message": str(exc)}
