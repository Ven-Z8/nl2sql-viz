"""Test loading the retail multi-table dataset."""
import asyncio
import time

from app.core.dataset_loader import list_datasets, load_dataset
from app.db.pool import PostgresPool

DSN = "postgresql://testuser:testpass@localhost:5432/testdb"


async def main() -> None:
    print("datasets:", [d["id"] for d in list_datasets()])
    pool = PostgresPool(dsn=DSN)
    await pool.connect()
    t0 = time.monotonic()
    info = await load_dataset(pool, "retail")
    print(f"loaded {info['name']} in {time.monotonic()-t0:.1f}s")
    print("tables:", info["tables"])
    print("questions:", {k: len(v) for k, v in info["questions"].items()})

    # Verify a join works
    r = await pool.execute("""
        SELECT c.region, COUNT(DISTINCT o.order_id) AS orders, SUM(oi.quantity * oi.unit_price) AS revenue
        FROM ds_retail_orders o
        JOIN ds_retail_customers c ON c.customer_id = o.customer_id
        JOIN ds_retail_order_items oi ON oi.order_id = o.order_id
        WHERE o.status = 'completed'
        GROUP BY c.region ORDER BY revenue DESC
    """)
    print("join result:", r.row_count, "rows")
    for row in r.rows[:3]:
        print("  ", row)
    await pool.disconnect()


if __name__ == "__main__":
    asyncio.run(main())