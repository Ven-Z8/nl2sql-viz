"""Load all datasets and verify joins work."""
import asyncio
import time

from app.core.dataset_loader import list_datasets, load_dataset
from app.db.pool import PostgresPool

DSN = "postgresql://testuser:testpass@localhost:5432/testdb"


async def main() -> None:
    pool = PostgresPool(dsn=DSN)
    await pool.connect()
    for d in list_datasets():
        t0 = time.monotonic()
        info = await load_dataset(pool, d["id"], DSN)
        print(f"{info['name']}: {len(info['tables'])} tables in {time.monotonic()-t0:.1f}s")
        print(f"  questions: {sum(len(v) for v in info['questions'].values())} total")
    await pool.disconnect()


if __name__ == "__main__":
    asyncio.run(main())