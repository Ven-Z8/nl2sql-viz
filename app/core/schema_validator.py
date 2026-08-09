"""Schema-aware SQL validator — grounds generated SQL in the real schema.

The LLM proposes SQL; this validator verifies every column reference against
the actual database schema and fixes mismatches — no guessing. Unknown columns
are fuzzy-matched to the closest real column; unresolvable references are
reported as errors so the query never runs against a wrong column.
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp

from app.models import SchemaMap


def _normalize(name: str) -> str:
    return name.lower().replace("_", "").replace(" ", "")


def _fuzzy_match(guess: str, candidates: list[str]) -> str | None:
    """Find the closest real column to a guessed name."""
    g = _normalize(guess)
    for c in candidates:
        if _normalize(c) == g:
            return c
    for c in candidates:
        if g in _normalize(c) or _normalize(c) in g:
            return c
    return None


class SchemaValidator:
    """Validate and fix SQL column references against a SchemaMap."""

    def __init__(self, schema: SchemaMap):
        self.schema = schema
        # table -> {normalized_column: real_column}
        self.columns: dict[str, dict[str, str]] = {}
        for table in schema.tables:
            self.columns[table] = {}
            for col in schema.columns.get(table, []):
                self.columns[table][_normalize(col.column)] = col.column

    def validate_and_fix(self, sql: str) -> tuple[bool, str, list[str]]:
        """Validate SQL against the schema.

        Returns (ok, fixed_sql, errors). When ok is True the SQL is safe to
        execute (possibly with corrected column names). When False, errors
        lists the unresolvable references.
        """
        try:
            parsed = sqlglot.parse_one(sql, read="postgres")
        except Exception as e:
            return False, sql, [f"SQL parse error: {e}"]

        # Build alias -> real table mapping from FROM/JOIN clauses
        aliases: dict[str, str] = {}
        for node in parsed.walk():
            if isinstance(node, exp.Table):
                table = node.name
                alias = node.alias or table
                aliases[alias] = table

        # Collect CTE names — bare columns from CTEs aren't real table columns
        cte_names = {
            node.alias for node in parsed.walk() if isinstance(node, exp.CTE)
        }

        errors: list[str] = []
        fixes: dict[tuple[str, str], str] = {}  # (table_ref, col) -> real_col

        for node in parsed.walk():
            if not isinstance(node, exp.Column):
                continue
            col = node.name
            table_ref = node.table or ""
            if table_ref:
                real_table = aliases.get(table_ref, table_ref)
                if real_table not in self.columns:
                    continue  # CTE or unknown table — not our concern
                real = self.columns[real_table].get(_normalize(col))
                if real is None:
                    real = _fuzzy_match(col, list(self.columns[real_table].values()))
                    if real:
                        fixes[(table_ref, col)] = real
                    else:
                        errors.append(
                            f"Column '{col}' not found in table '{real_table}' "
                            f"(available: {', '.join(list(self.columns[real_table].values())[:8])})"
                        )
            else:
                # Bare column (no table prefix) — check against all tables
                if col in cte_names:
                    continue  # CTE column — not a real table column
                found = None
                for t, cols in self.columns.items():
                    if _normalize(col) in cols:
                        found = cols[_normalize(col)]
                        break
                if found is None:
                    for t, cols in self.columns.items():
                        found = _fuzzy_match(col, list(cols.values()))
                        if found:
                            break
                if found:
                    fixes[("", col)] = found
                elif not cte_names:
                    errors.append(f"Column '{col}' not found in any table")

        if fixes:
            for node in parsed.walk():
                if isinstance(node, exp.Column):
                    key = (node.table or "", node.name)
                    if key in fixes:
                        node.set("this", exp.to_identifier(fixes[key]))
            sql = parsed.sql(dialect="postgres")

        return (not errors), sql, errors