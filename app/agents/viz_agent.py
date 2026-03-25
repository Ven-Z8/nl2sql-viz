import json
import re
from decimal import Decimal
from typing import Any

from anthropic import AsyncAnthropic


def _default_serializer(obj: Any) -> Any:
    """JSON serializer for types not handled by the default encoder."""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

VIZ_SYSTEM_PROMPT = """You are a data visualization expert. Given query results and the original question,
generate a valid Vega-Lite v5 JSON specification.

Rules:
- Return ONLY the JSON object — no explanation, no markdown, no backticks
- Use "$schema": "https://vega.github.io/schema/vega-lite/v5.json"
- Embed the data inline in "data": {"values": [...]}
- Choose the most appropriate mark type (bar, line, point, arc) for the data shape
- Add a descriptive title derived from the question
- Use proper axis labels"""


class VizAgent:
    """Generates Vega-Lite v5 specifications from query results."""

    def __init__(self) -> None:
        self._client = AsyncAnthropic()

    async def run(self, nl_query: str, rows: list[dict[str, Any]]) -> str:
        """
        Generate a Vega-Lite spec from natural language query and data rows.

        Args:
            nl_query: Natural language description of the visualization
            rows: List of data rows (dicts) from query result

        Returns:
            Valid Vega-Lite v5 JSON string

        Raises:
            ValueError: If the response is not valid JSON
        """
        user_msg = f"Question: {nl_query}\n\nData:\n{json.dumps(rows, indent=2, default=_default_serializer)}"

        response = await self._client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=VIZ_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text.strip()

        # Remove markdown code fence if present
        raw = re.sub(r"^```json\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"```$", "", raw).strip()

        # Validate JSON
        try:
            json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid Vega-Lite JSON from Viz Agent: {e}") from e

        return raw
