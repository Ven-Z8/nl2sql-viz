# NOTE: Uses Anthropic SDK directly for Plan 1 simplicity.
# Will be refactored to Claude Agent SDK in a later plan when subagent orchestration is needed.
import re
from typing import Any

from anthropic import Anthropic

from app.connectors.base import BaseConnector

_client = Anthropic()

SQL_SYSTEM_PROMPT = """You are a SQL expert. Given a natural language query and a database schema,
write a single valid PostgreSQL SELECT query that answers the question.
Return ONLY the SQL query — no explanation, no markdown, no backticks.
The query must be a SELECT or WITH statement."""


class SQLAgent:
    def __init__(self, connector: BaseConnector, max_retries: int = 3):
        self._connector = connector
        self._max_retries = max_retries

    async def run(self, nl_query: str, schema_map: str) -> dict[str, Any]:
        messages: list[dict[str, str]] = []
        last_error: str | None = None

        for attempt in range(1, self._max_retries + 1):
            user_msg = f"Schema:\n{schema_map}\n\nQuestion: {nl_query}"
            if last_error:
                user_msg += f"\n\nPrevious SQL failed with: {last_error}\nWrite a corrected query."

            messages.append({"role": "user", "content": user_msg})

            response = _client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=SQL_SYSTEM_PROMPT,
                messages=messages,
            )
            sql = response.content[0].text.strip()
            sql = re.sub(r"^```sql\s*", "", sql, flags=re.IGNORECASE)
            sql = re.sub(r"```$", "", sql).strip()

            messages.append({"role": "assistant", "content": sql})

            try:
                rows = await self._connector.execute_read(sql)
                return {"status": "success", "sql": sql, "rows": rows, "attempts": attempt}
            except Exception as e:
                last_error = str(e)

        return {
            "status": "error",
            "message": f"Could not generate a working query after {self._max_retries} attempts.",
            "last_error": last_error,
            "attempts": self._max_retries,
        }
