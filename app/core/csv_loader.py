"""CSV ingestion — parse, infer types, and load into Postgres.

Uploaded CSVs become real tables in the demo database so the existing
NL2SQL pipeline (schema introspection → SQL generation → execution) works
on them unchanged.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from typing import Any

from app.db.pool import PostgresPool

_MAX_ROWS = 1_000_000  # safety cap on uploaded rows
_SAMPLE_SIZE = 1000  # rows used for type inference


class CSVUploadError(ValueError):
    """Raised when a CSV cannot be parsed or loaded."""


def sanitize_table_name(filename: str) -> str:
    """Turn a filename into a safe Postgres table name."""
    base = re.sub(r"\.csv$", "", filename, flags=re.IGNORECASE)
    base = re.sub(r"[^a-zA-Z0-9_]+", "_", base).strip("_").lower()
    if not base:
        raise CSVUploadError("Could not derive a table name from the filename")
    return f"upload_{base[:48]}"


def _is_int(value: str) -> bool:
    try:
        int(value)
        return True
    except ValueError:
        return False


def _is_float(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def _is_date(value: str) -> bool:
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            datetime.strptime(value, fmt)
            return True
        except ValueError:
            continue
    return False


def _is_timestamp(value: str) -> bool:
    for fmt in (
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
        "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M",
        "%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M",
    ):
        try:
            datetime.strptime(value, fmt)
            return True
        except ValueError:
            continue
    return False


def _infer_type(values: list[str]) -> str:
    """Infer a Postgres column type from a sample of string values."""
    non_empty = [v for v in values if v and v.strip()]
    if not non_empty:
        return "TEXT"
    if all(_is_int(v) for v in non_empty):
        return "BIGINT"
    if all(_is_float(v) for v in non_empty):
        return "DOUBLE PRECISION"
    if all(_is_timestamp(v) for v in non_empty):
        return "TIMESTAMP"
    if all(_is_date(v) for v in non_empty):
        return "DATE"
    return "TEXT"


def _coerce(value: str, col_type: str) -> Any:
    """Coerce a raw string to the inferred column type."""
    if value is None or value == "":
        return None
    if col_type == "BIGINT":
        return int(value)
    if col_type == "DOUBLE PRECISION":
        return float(value)
    if col_type == "TIMESTAMP":
        for fmt in (
            "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
            "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M",
            "%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M",
        ):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None
    if col_type == "DATE":
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        return None
    return value


def parse_csv(content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    """Parse CSV bytes into (columns, rows-as-dicts)."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise CSVUploadError("File must be UTF-8 encoded CSV")
    reader = csv.DictReader(io.StringIO(text))
    columns = reader.fieldnames or []
    if not columns:
        raise CSVUploadError("CSV has no header row")
    rows = [dict(r) for r in reader]
    if not rows:
        raise CSVUploadError("CSV has no data rows")
    if len(rows) > _MAX_ROWS:
        raise CSVUploadError(f"CSV exceeds the {_MAX_ROWS:,} row limit")
    return columns, rows


def infer_schema(columns: list[str], rows: list[dict[str, str]]) -> dict[str, str]:
    """Infer a Postgres type per column from a sample of rows."""
    types: dict[str, str] = {}
    for col in columns:
        values = [r.get(col, "") for r in rows[:_SAMPLE_SIZE]]
        types[col] = _infer_type(values)
    return types


async def load_csv(
    pool: PostgresPool,
    table_name: str,
    columns: list[str],
    rows: list[dict[str, str]],
    types: dict[str, str],
) -> int:
    """Create the table and bulk-load all rows via COPY. Returns row count."""
    col_defs = ", ".join(f'"{c}" {types[c]}' for c in columns)
    await pool.execute_raw(f'DROP TABLE IF EXISTS "{table_name}"')
    await pool.execute_raw(f'CREATE TABLE "{table_name}" ({col_defs})')

    records = (
        [_coerce(row.get(c, ""), types[c]) for c in columns]
        for row in rows
    )
    await pool.copy_records(table_name, columns, records)
    return len(rows)
