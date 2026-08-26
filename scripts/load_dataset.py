"""Load one dataset by id."""
import asyncio
import sys
import time

from app.core.dataset_loader import load_dataset
from app.db.pool import PostgresPool

DSN = "postgresql://testuser:testpass@localhost:5432/testdb"


async def main() -> None:
    dataset_id = sys.argv[1] if len(sys.argv) > 1 else "olist"
    pool = PostgresPool(dsn=DSN)
    await pool.connect()
    t0 = time.monotonic()
    info = await load_dataset(pool, dataset_id)
    print(f"{info['name']}: {len(info['tables'])} tables in {time.monotonic()-t0:.1f}s")
    for t in info["tables"]:
        result = await pool.execute(f'SELECT count(*) AS n FROM "ds_{dataset_id}_{t}"')
        print(f"  ds_{dataset_id}_{t}: {result.rows[0]['n']:,} rows")
    await pool.disconnect()


if __name__ == "__main__":
    asyncio.run(main())