"""Seed the deploy Postgres with all datasets + samples (idempotent).

Loads every committed dataset (data/datasets/*/schema.json + CSVs) and the
sample CSVs (data/samples/manifest.json) into the DATABASE_URL database.
Safe to re-run — each table is dropped and re-created.

Usage (Render job or locally):
    DATABASE_URL=... python scripts/seed_deploy.py
"""
import asyncio
import os
import time

from app.core.dataset_loader import list_datasets, load_dataset
from app.core.samples import list_samples, load_sample
from app.db.pool import PostgresPool


async def main() -> None:
    dsn = os.getenv("DATABASE_URL") or os.getenv("DEMO_DATABASE_URL")
    if not dsn:
        raise SystemExit("DATABASE_URL is required")
    pool = PostgresPool(dsn=dsn)
    await pool.connect()

    for d in list_datasets():
        t0 = time.monotonic()
        try:
            info = await load_dataset(pool, d["id"])
            print(f"dataset {d['id']}: {len(info['tables'])} tables in {time.monotonic()-t0:.0f}s")
        except Exception as e:  # noqa: BLE001
            print(f"dataset {d['id']}: FAILED {type(e).__name__}: {str(e)[:120]}")

    for s in list_samples():
        t0 = time.monotonic()
        try:
            info = await load_sample(pool, s["id"])
            print(f"sample {s['id']}: {info.get('row_count', '?')} rows in {time.monotonic()-t0:.0f}s")
        except Exception as e:  # noqa: BLE001
            print(f"sample {s['id']}: FAILED {type(e).__name__}: {str(e)[:120]}")

    await pool.disconnect()
    print("seed complete")


if __name__ == "__main__":
    asyncio.run(main())