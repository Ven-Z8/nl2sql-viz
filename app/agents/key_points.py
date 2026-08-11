"""KeyPointsAgent — synthesizes an analyst narrative from grounded numbers.

After the pipeline has executed the queries, this fast-model agent reads the
question + the grounded metrics/report sections and writes 2-4 key points that
tell the story. It is STRICTLY grounded: it may only reference the numbers it
is given — never invent, estimate, or compute new figures. The numbers
themselves come from executed query results, so the narrative stays truthful.
"""

from __future__ import annotations

import json
import re

from nooa import Agent

from app.llm import HAIKU

_SYSTEM_PROMPT = """You are a senior data analyst. Given a question and the grounded numbers
from the query results, write 2-4 concise key points that tell the story.

Rules:
- ONLY use the numbers provided — never invent, estimate, or compute new figures
- Each key point must reference at least one provided number
- Be specific: name the largest/smallest, the direction of change, the biggest driver
- No filler, no marketing language, no hedging
- If a comparison or trend is present, state which side wins and by how much

Respond with ONLY a JSON object: {"key_points": ["point 1", "point 2", ...]}
No commentary, no markdown fences."""


def _parse_key_points(content: str) -> list[str]:
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"[\[{]", text)
        if not match:
            return []
        try:
            data = json.loads(text[match.start():])
        except json.JSONDecodeError:
            return []
    if isinstance(data, dict):
        data = data.get("key_points", data.get("points", []))
    if not isinstance(data, list):
        return []
    return [str(p).strip() for p in data if str(p).strip()][:4]


class KeyPointsAgent(Agent, llm=HAIKU):
    """You are a senior data analyst who writes key points from grounded numbers."""

    async def synthesize(self, question: str, numbers_text: str) -> list[str]:
        """Write 2-4 key points from ``numbers_text`` (grounded metrics/sections).

        No ``response_format`` is passed — Ling flash's providers disagree on
        whether they support json_object/json_schema, so the JSON is prompted
        for and parsed defensively instead.
        """
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Question: {question}\n\nGrounded numbers:\n{numbers_text}",
            },
        ]
        response = await self.llm.acall(messages, max_tokens=400)
        content = response.content
        if not isinstance(content, str):
            return []
        points = _parse_key_points(content)
        if not points:
            # One retry — cheap models occasionally emit a malformed first pass
            response = await self.llm.acall(messages, max_tokens=400)
            content = response.content
            if isinstance(content, str):
                points = _parse_key_points(content)
        return points


def metrics_to_text(metrics, sections=None, rows=None) -> str:
    """Render grounded metrics + report sections + top result rows for the synthesizer."""
    lines: list[str] = []
    if rows:
        for r in rows[:5]:
            parts = [f"{k}: {v}" for k, v in list(r.items())[:5]]
            lines.append(f"- {', '.join(parts)}")
    for m in metrics:
        lines.append(f"- {m.label}: {m.value:,.2f}")
    if sections:
        for s in sections:
            lines.append(f"- [{s.title}] {s.text}")
    return "\n".join(lines) if lines else "No numeric metrics were computed."
