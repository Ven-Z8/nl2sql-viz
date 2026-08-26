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


def metrics_to_text(metrics, sections=None, rows=None, metric_tags=None) -> str:
    """Render grounded metrics + report sections + top result rows for the synthesizer.

    ``metric_tags`` (aligned with ``metrics``) carries source ids like
    ``[q0.r2]`` so the model sees exactly which shipped result set each number
    came from — and only tagged (traceable) numbers are offered at all.
    """
    lines: list[str] = []
    if rows:
        for r in rows[:5]:
            parts = [f"{k}: {v}" for k, v in list(r.items())[:5]]
            lines.append(f"- {', '.join(parts)} [q0]")
    for i, m in enumerate(metrics):
        tag = metric_tags[i] if metric_tags and i < len(metric_tags) else ""
        suffix = f" {tag}" if tag else ""
        lines.append(f"- {m.label}: {m.value:,.2f}{suffix}")
    if sections:
        for s in sections:
            lines.append(f"- [{s.title}] {s.text}")
    return "\n".join(lines) if lines else "No numeric metrics were computed."


# ---------------------------------------------------------------------------
# Grounded-number enforcement for the narrative
# ---------------------------------------------------------------------------

_NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
# Years are context words in analyst prose ("grew in 2024"), not cited metrics;
# demanding a data trace for them would drop valid points over dates that are
# stored as strings in result rows.
_YEAR_MIN, _YEAR_MAX = 1900, 2100


def extract_numbers(text: str) -> list[float]:
    """Parse every plain number out of ``text`` (comma separators tolerated)."""
    values: list[float] = []
    for match in _NUMBER_RE.finditer(text):
        raw = match.group(0).replace(",", "")
        try:
            values.append(float(raw))
        except ValueError:  # pragma: no cover — regex only emits valid floats
            continue
    return values


def _matches_traceable(value: float, traceable: set[float]) -> bool:
    """Same tolerance the reference harness uses: 1 unit or 1%."""
    return any(abs(value - t) <= max(1.0, abs(t) * 0.01) for t in traceable)


def filter_key_points_grounded(points: list[str], traceable: set[float]) -> list[str]:
    """Drop key points that cite numbers absent from the shipped result sets.

    Every number a point mentions must match a traceable value (or be a bare
    year used as context). This is the hard backstop that keeps the narrative
    from inventing or misquoting figures.
    """
    kept: list[str] = []
    for point in points:
        ok = True
        for value in extract_numbers(point):
            if value.is_integer() and _YEAR_MIN <= value <= _YEAR_MAX:
                continue  # bare-year context — allowed without a data trace
            if not _matches_traceable(value, traceable):
                ok = False
                break
        if ok:
            kept.append(point)
    return kept


def traceable_values(metrics, sections=None, rows=None) -> set[float]:
    """Collect every number the answer is allowed to cite.

    Metric values, report-section metric values, and numeric cells of the
    shipped result rows all count; anything else in the narrative is
    ungrounded and gets filtered.
    """
    values: set[float] = set()
    for m in metrics:
        values.add(float(m.value))
    if sections:
        for s in sections:
            for m in s.metrics:
                values.add(float(m.value))
    if rows:
        for row in rows:
            for v in row.values():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    values.add(float(v))
    return values
