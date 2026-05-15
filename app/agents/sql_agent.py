import re
from typing import Any

from anthropic import AsyncAnthropic

from app.connectors.base import BaseConnector

SQL_SYSTEM_PROMPT = """You are a senior PostgreSQL analytics engineer for a BI copilot.
Given a natural language business question and a compact database schema, write one
safe, correct PostgreSQL query that answers the question.

Hard rules:
- Return ONLY the SQL query. No explanation, markdown, comments, or backticks.
- The query must be a single read-only SELECT or WITH statement.
- Do not use SELECT *.
- Use explicit JOIN conditions from the schema relationships when available.
- Choose the correct grain before aggregating. Avoid accidental fanout from joins.
- Use clear aliases for computed metrics and dimensions.
- For time-series questions, use DATE_TRUNC at the requested grain and ORDER BY time.
- For ranking or "top/highest" questions, order by the metric and use a sensible LIMIT.
- For averages and rates, guard division with NULLIF when needed.
- When filtering text values from user wording, prefer case-insensitive comparisons
  such as LOWER(column) = LOWER('value') unless exact casing is known from schema context.
- Preserve NULL semantics unless the question asks to exclude NULLs.
- Prefer simple SQL over clever SQL when both are correct.

If a previous attempt failed, correct the SQL using the database error while keeping
the same business intent."""


class SQLAgent:
    def __init__(self, connector: BaseConnector, max_retries: int = 3):
        self._connector = connector
        self._max_retries = max_retries
        self._client = AsyncAnthropic()

    async def run(self, nl_query: str, schema_map: str) -> dict[str, Any]:
        messages: list[dict[str, str]] = []
        last_error: str | None = None

        for attempt in range(1, self._max_retries + 1):
            user_msg = f"Schema:\n{schema_map}\n\nQuestion: {nl_query}"
            if last_error:
                user_msg += f"\n\nPrevious SQL failed with: {last_error}\nWrite a corrected query."

            messages.append({"role": "user", "content": user_msg})

            response = await self._client.messages.create(
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
                if not rows and attempt < self._max_retries:
                    last_error = (
                        "The SQL ran successfully but returned zero rows. "
                        "This may be caused by an exact text value or casing mismatch. "
                        "Retry with case-insensitive text filters or a broader predicate "
                        "while preserving the user's business intent."
                    )
                    continue
                return {"status": "success", "sql": sql, "rows": rows, "attempts": attempt}
            except Exception as e:
                last_error = str(e)

        return {
            "status": "error",
            "message": f"Could not generate a working query after {self._max_retries} attempts.",
            "last_error": last_error,
            "attempts": self._max_retries,
        }
