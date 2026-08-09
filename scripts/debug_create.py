"""Debug the dataset loader's CREATE statement."""
import asyncio
import json

from app.core.dataset_loader import _table_name
from app.db.pool import PostgresPool

DSN = "postgresql://testuser:testpass@localhost:5432/testdb"


async def main() -> None:
    with open("data/datasets/retail/schema.json") as f:
        schema = json.load(f)
    customers = schema["tables"][0]
    print("customers table:", json.dumps(customers, indent=1))
    col_defs = []
    for c in customers["columns"]:
        col = f'"{c["name"]}" {c["type"]}'
        if c.get("pk"):
            col += " PRIMARY KEY"
        col_defs.append(col)
    print("CREATE:", f'CREATE TABLE "{_table_name("retail", "customers")}" ({", ".join(col_defs)})')

    pool = PostgresPool(dsn=DSN)
    await pool.connect()
    await pool.execute_raw(f'DROP TABLE IF EXISTS "{_table_name("retail", "customers")}" CASCADE')
    await pool.execute_raw(f'CREATE TABLE "{_table_name("retail", "customers")}" ({", ".join(col_defs)})')
    r = await pool.execute(
        "SELECT conname, contype FROM pg_constraint "
        f"WHERE conrelid = '{_table_name('retail', 'customers')}'::regclass"
    )
    print("constraints:", [(x["conname"], x["contype"]) for x in r.rows])
    await pool.disconnect()


if __name__ == "__main__":
    asyncio.run(main())