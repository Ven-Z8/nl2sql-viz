"""Reproduce the big CSV load to find the error."""
import asyncio

from app.core.csv_loader import infer_schema, load_csv, parse_csv
from app.db.pool import PostgresPool

DSN = "postgresql://testuser:testpass@localhost:5432/testdb"


async def main() -> None:
    content = open("data/samples/finance_lending.csv", "rb").read()
    print("parsing...")
    columns, rows = parse_csv(content)
    print(f"parsed: {len(columns)} cols, {len(rows)} rows")
    types = infer_schema(columns, rows)
    print("types inferred")
    pool = PostgresPool(dsn=DSN)
    await pool.connect()
    try:
        n = await load_csv(pool, "upload_finance_lending", columns, rows, types)
        print("loaded:", n)
    except Exception as e:
        print("ERROR:", type(e).__name__, str(e)[:800])
    finally:
        await pool.disconnect()


if __name__ == "__main__":
    asyncio.run(main())