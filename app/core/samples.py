"""Sample datasets — bundled CSVs for one-click demo loading.

Samples live in data/samples/ with a manifest.json describing each one.
Loading a sample runs the same pipeline as a user upload (parse → infer →
COPY into Postgres), so the demo works without a file picker.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.core.csv_loader import infer_schema, load_csv, parse_csv
from app.db.pool import PostgresPool

_SAMPLES_DIR = Path(__file__).resolve().parents[2] / "data" / "samples"


def _load_manifest() -> dict[str, dict[str, str]]:
    with open(_SAMPLES_DIR / "manifest.json", encoding="utf-8") as f:
        return json.load(f)


def list_samples() -> list[dict[str, str]]:
    """Return the available sample datasets for the UI."""
    manifest = _load_manifest()
    samples: list[dict[str, str]] = []
    for sample_id, meta in manifest.items():
        if (_SAMPLES_DIR / f"{sample_id}.csv").exists():
            samples.append({
                "id": sample_id,
                "name": meta["name"],
                "domain": meta["domain"],
                "description": meta["description"],
            })
    return samples


async def load_sample(pool: PostgresPool, sample_id: str, dsn: str) -> dict:
    """Load a sample CSV into Postgres. Returns the same shape as /api/upload."""
    manifest = _load_manifest()
    if sample_id not in manifest:
        raise KeyError(sample_id)
    meta = manifest[sample_id]
    csv_path = _SAMPLES_DIR / f"{sample_id}.csv"
    content = csv_path.read_bytes()
    columns, rows = parse_csv(content)
    types = infer_schema(columns, rows)
    table_name = f"upload_{sample_id}"
    row_count = await load_csv(pool, table_name, columns, rows, types)
    return {
        "table_name": table_name,
        "row_count": row_count,
        "columns": columns,
        "types": types,
        "domain": meta["domain"],
        "preview": rows[:5],
        "dsn": dsn,
        "questions": meta.get("questions", []),
    }