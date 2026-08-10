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
        # table -> {exact_column: exact_column} — case-sensitive exact matches
        self.columns: dict[str, dict[str, str]] = {}
        # table -> {normalized_column: exact_column} — for case-insensitive/fuzzy fixes
        self.normalized: dict[str, dict[str, str]] = {}
        for table in schema.tables:
            self.columns[table] = {}
            self.normalized[table] = {}
            for col in schema.columns.get(table, []):
                self.columns[table][col.column] = col.column
                self.normalized[table][_normalize(col.column)] = col.column

    def _resolve(self, table: str, col: str) -> str | None:
        """Resolve a column reference to the real column name.

        Exact (case-sensitive) match wins; a case-insensitive or fuzzy match
        returns the real name so the caller can fix the reference. Postgres
        treats quoted identifiers case-sensitively, so ``state`` must be
        rewritten to ``"State"`` — never passed through as-is.
        """
        real = self.columns[table].get(col)
        if real is not None:
            return real
        real = self.normalized[table].get(_normalize(col))
        if real is not None:
            return real
        return _fuzzy_match(col, list(self.columns[table].values()))

    @staticmethod
    def _needs_fix(real: str, col: str) -> bool:
        """A reference needs rewriting when it differs from the real name OR
        the real name has uppercase — unquoted identifiers fold to lowercase
        in Postgres, so ``State`` must render as ``"State"``."""
        return real != col or real != real.lower()

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

        # Tables the query actually reads — bare columns must exist in one of
        # these, not anywhere in the database (a column that exists in an
        # unrelated table must not validate a wrong reference).
        active_tables = {t for t in aliases.values() if t in self.columns}

        # Collect CTE names and SELECT aliases — these are computed columns, not
        # real table columns, so references to them must be skipped.
        cte_names = {
            node.alias for node in parsed.walk() if isinstance(node, exp.CTE)
        }
        select_aliases = {
            node.alias for node in parsed.walk()
            if isinstance(node, exp.Alias) and node.alias
        }

        errors: list[str] = []
        fixes: dict[tuple[str, str], str] = {}  # (table_ref, col) -> real_col

        for node in parsed.walk():
            if not isinstance(node, exp.Column):
                continue
            col = node.name
            if col in select_aliases:
                continue  # computed column (SELECT alias) — not a table column
            table_ref = node.table or ""
            if table_ref:
                real_table = aliases.get(table_ref, table_ref)
                if real_table not in self.columns:
                    continue  # CTE or unknown table — not our concern
                real = self._resolve(real_table, col)
                if real is not None:
                    if self._needs_fix(real, col):
                        fixes[(table_ref, col)] = real
                else:
                    errors.append(
                        f"Column '{col}' not found in table '{real_table}' "
                        f"(available: {', '.join(list(self.columns[real_table].values())[:8])})"
                    )
            else:
                # Bare column (no table prefix) — check against the query's
                # active tables only
                if col in cte_names:
                    continue  # CTE column — not a real table column
                found = None
                for t in active_tables:
                    found = self._resolve(t, col)
                    if found is not None:
                        break
                if found is not None:
                    if self._needs_fix(found, col):
                        fixes[("", col)] = found
                elif not cte_names and active_tables:
                    errors.append(
                        f"Column '{col}' not found in table(s) "
                        f"{', '.join(sorted(active_tables))}"
                    )

        if fixes:
            for node in parsed.walk():
                if isinstance(node, exp.Column):
                    key = (node.table or "", node.name)
                    if key in fixes:
                        # Always quote: unquoted identifiers fold to lowercase
                        # in Postgres, so "State" must render as "State".
                        node.set("this", exp.to_identifier(fixes[key], quoted=True))
            sql = parsed.sql(dialect="postgres")

        return (not errors), sql, errors