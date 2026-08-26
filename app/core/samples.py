"""Sample datasets — bundled CSVs for one-click demo loading.

Samples live in data/samples/ with a manifest.json describing each one.
Loading a sample runs the same pipeline as a user upload (parse → infer →
COPY into Postgres), so the demo works without a file picker.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.core.csv_loader import infer_schema, iter_csv, load_csv
from app.db.pool import PostgresPool

_SAMPLES_DIR = Path(__file__).resolve().parents[2] / "data" / "samples"
_SAMPLE_SIZE = 1000


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


async def load_sample(pool: PostgresPool, sample_id: str) -> dict:
    """Load a sample CSV into Postgres. Returns the same shape as /api/upload
    (no DSN — callers attach the registry's connection_id)."""
    manifest = _load_manifest()
    if sample_id not in manifest:
        raise KeyError(sample_id)
    meta = manifest[sample_id]
    csv_path = _SAMPLES_DIR / f"{sample_id}.csv"

    # Stream the CSV — memory-safe for large files (e.g. 2.2M-row Lending Club)
    columns, rows = iter_csv(str(csv_path))
    sample: list[dict[str, str]] = []
    for i, row in enumerate(rows):
        if i >= _SAMPLE_SIZE:
            break
        sample.append(row)
    types = infer_schema(columns, sample)

    table_name = f"upload_{sample_id}"
    _, rows = iter_csv(str(csv_path))  # fresh iterator for the full load
    row_count = await load_csv(pool, table_name, columns, rows, types)
    return {
        "table_name": table_name,
        "row_count": row_count,
        "columns": columns,
        "types": types,
        "domain": meta["domain"],
        "preview": sample[:5],
        "questions": meta.get("questions", []),
    }