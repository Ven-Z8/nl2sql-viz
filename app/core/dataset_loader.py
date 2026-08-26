"""Multi-table dataset loader — loads complex relational datasets into Postgres.

A dataset is a directory with schema.json (table definitions + FKs), one CSV
per table, and questions.json (the difficulty ladder). Loading creates the
tables with primary/foreign keys and streams each CSV via COPY.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.core.csv_loader import iter_csv, load_csv
from app.db.pool import PostgresPool

_DATASETS_DIR = Path(__file__).resolve().parents[2] / "data" / "datasets"


def _read_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def list_datasets() -> list[dict[str, str]]:
    """List available datasets (directories with schema.json)."""
    datasets: list[dict[str, str]] = []
    for d in sorted(_DATASETS_DIR.iterdir()):
        schema_path = d / "schema.json"
        if d.is_dir() and schema_path.exists():
            schema = _read_json(schema_path)
            datasets.append({
                "id": d.name,
                "name": schema.get("name", d.name),
                "domain": schema.get("domain", "general"),
                "description": schema.get("description", ""),
            })
    return datasets


def _table_name(dataset_id: str, table: str) -> str:
    return f"ds_{dataset_id}_{table}"


def _pick_focus(tables: list[dict]) -> str:
    """Choose the dataset's focus table — the FK-graph hub.

    Schema scoping walks foreign keys outward from the focus table, so the
    hub (most FK edges, counting both directions) reaches the largest slice
    of the dataset. For a star schema this is the fact table; for worldbank
    it's ``values`` joining countries+indicators.
    """
    if not tables:
        raise KeyError("dataset has no tables")
    degree: dict[str, int] = {t["name"]: 0 for t in tables}
    for t in tables:
        for c in t["columns"]:
            fk = c.get("fk")
            if fk:
                degree[t["name"]] += 1
                degree[fk.split(".")[0]] += 1
    return max(degree, key=degree.get)


async def load_dataset(pool: PostgresPool, dataset_id: str) -> dict:
    """Load a multi-table dataset into Postgres. Returns dataset info.

    Contains NO DSN — callers attach the opaque connection_id from the
    server-side registry instead.
    """
    dataset_dir = _DATASETS_DIR / dataset_id
    schema_path = dataset_dir / "schema.json"
    if not schema_path.exists():
        raise KeyError(dataset_id)
    schema = _read_json(schema_path)
    questions = _read_json(dataset_dir / "questions.json")

    tables = schema["tables"]
    # Create tables in dependency order (parents before children)
    created: set[str] = set()
    for table in tables:
        fk_refs = [c["fk"] for c in table["columns"] if "fk" in c]
        # Simple topological sort: retry until all FKs resolve
        for _ in range(len(tables) + 1):
            if table["name"] in created:
                break
            if all(fk.split(".")[0] in created for fk in fk_refs):
                await _create_and_load(pool, dataset_id, table, dataset_dir)
                created.add(table["name"])
                break

    return {
        "dataset_id": dataset_id,
        "name": schema.get("name", dataset_id),
        "domain": schema.get("domain", "general"),
        "tables": [t["name"] for t in tables],
        # Qualified focus table — clients echo it back on queries so schema
        # scoping stays inside this dataset's FK graph instead of the whole DB.
        "focus_table": _table_name(dataset_id, _pick_focus(tables)),
        "questions": questions,
    }


async def _create_and_load(pool: PostgresPool, dataset_id: str, table: dict, dataset_dir: Path) -> None:
    """Create one table (with PK/FK) and stream its CSV."""
    table_name = _table_name(dataset_id, table["name"])
    col_defs = []
    for c in table["columns"]:
        col = f'"{c["name"]}" {c["type"]}'
        if c.get("pk"):
            col += " PRIMARY KEY"
        if "fk" in c:
            ref_table, ref_col = c["fk"].split(".")
            col += f' REFERENCES "{_table_name(dataset_id, ref_table)}" ("{ref_col}")'
        col_defs.append(col)

    await pool.execute_raw(f'DROP TABLE IF EXISTS "{table_name}" CASCADE')
    await pool.execute_raw(f'CREATE TABLE "{table_name}" ({", ".join(col_defs)})')

    csv_path = dataset_dir / f"{table['name']}.csv"
    columns, rows = iter_csv(str(csv_path))
    types = {c["name"]: c["type"] for c in table["columns"]}
    await load_csv(pool, table_name, columns, rows, types, create=False)