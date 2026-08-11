"""SchemaLinker — grounds a question in the real schema using a fast model.

The schema-linking step: a small, fast LLM reads the question + full schema
and identifies the tables and columns that matter. The main SQL model then
generates against ONLY the linked schema — a small, correct context instead
of guessing across hundreds of columns. Domain-agnostic: works on any
database, no manual metric definitions.

Note: implemented as a plain method (not PredictStrategy) because the fast
model (Ling flash via OpenRouter) rejects ``json_schema`` response formats —
it only supports ``json_object``. The JSON is parsed and validated here
instead of relying on the provider's structured-output enforcement.
"""

from __future__ import annotations

import json
import re

from nooa import Agent

from app.llm import HAIKU
from app.models import LinkedTable

_SYSTEM_PROMPT = """You are a database schema linker. Given a question and a database schema,
identify the tables and columns needed to answer it.

Rules:
- Only return tables and columns that EXIST in the schema
- Include join keys (foreign keys) needed to connect the tables
- Include the columns needed for filters, grouping, and aggregation
- Be selective — do not return every column, only the relevant ones
- Return an empty JSON array [] if no table is relevant

Respond with ONLY a JSON array of objects, each with exactly two keys:
{"table": "<table name>", "columns": ["<column>", ...]}
No commentary, no markdown fences."""


def _parse_linked(content: str) -> list[LinkedTable]:
    """Parse the model's JSON into LinkedTable entries, defensively."""
    text = content.strip()
    # Strip markdown code fences if the model ignored the instruction
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Reasoning models sometimes prefix their JSON with thinking text —
        # parse the first JSON value embedded in the response
        match = re.search(r"[\[{]", text)
        if not match:
            return []
        try:
            data = json.loads(text[match.start():])
        except json.JSONDecodeError:
            return []
    if isinstance(data, dict):
        # Accept {"value": [...]} or {"tables": [...]} wrappers
        data = data.get("value", data.get("tables", []))
    if not isinstance(data, list):
        return []
    linked: list[LinkedTable] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        try:
            linked.append(LinkedTable(table=str(entry["table"]), columns=list(entry.get("columns", []))))
        except (KeyError, TypeError, ValueError):
            continue
    return linked


class SchemaLinker(Agent, llm=HAIKU):
    """You are a database schema linker. Given a question and a database schema,
    identify the tables and columns needed to answer it."""

    async def link(self, question: str, schema_text: str) -> list[LinkedTable]:
        """Identify the tables and columns relevant to ``question``.

        Calls the fast model and validates the parsed JSON here. No
        ``response_format`` — Ling flash's providers (DeepInfra/Novita)
        disagree on json_object/json_schema support, so the JSON is prompted
        for and parsed defensively.
        """
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Question: {question}\n\nDatabase schema:\n{schema_text}",
            },
        ]
        response = await self.llm.acall(messages, max_tokens=2000)
        content = response.content
        if not isinstance(content, str):
            return []
        linked = _parse_linked(content)
        if not linked:
            # One retry — cheap models occasionally emit a malformed first pass
            response = await self.llm.acall(messages, max_tokens=2000)
            content = response.content
            if isinstance(content, str):
                linked = _parse_linked(content)
        return linked