"""SQL Guard — validates that generated SQL is safe for execution.

Multi-layer safety:
1. Syntax check: only SELECT / WITH allowed
2. Keyword blocklist: no mutating operations
3. Single statement only
"""

from __future__ import annotations

import re

_FIRST_TOKEN_RE = re.compile(r"^\s*([a-zA-Z]+)")
_MUTATING_KEYWORD_RE = re.compile(
    r"\b("
    r"alter|call|copy|create|delete|do|drop|execute|grant|insert|merge|"
    r"reindex|revoke|set|truncate|update|vacuum"
    r")\b",
    re.IGNORECASE,
)


def validate_read_only(sql: str) -> None:
    """Raise ValueError unless sql is a single read-only SELECT/WITH statement."""
    stripped = sql.strip()
    if not stripped:
        raise ValueError("SQL query is empty")

    if ";" in stripped.rstrip(";"):
        raise ValueError("Only a single statement is allowed")

    first_token = _FIRST_TOKEN_RE.match(stripped)
    if first_token is None or first_token.group(1).upper() not in {"SELECT", "WITH"}:
        raise ValueError("read-only queries only (SELECT or WITH)")

    without_semicolon = stripped.removesuffix(";")
    mutating = _MUTATING_KEYWORD_RE.search(without_semicolon)
    if mutating:
        raise ValueError(f"SQL contains mutating keyword: {mutating.group(1).upper()}")
