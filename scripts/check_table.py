"""Check the ds_retail_customers table state."""
import asyncio

from app.db.pool import PostgresPool

DSN = "postgresql://testuser:testpass@localhost:5432/testdb"


async def main() -> None:
    pool = PostgresPool(dsn=DSN)
    await pool.connect()
    r = await pool.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name = 'ds_retail_customers' ORDER BY ordinal_position"
    )
    print("columns:", [(x["column_name"], x["data_type"]) for x in r.rows])
    r2 = await pool.execute(
        "SELECT conname, contype FROM pg_constraint "
        "WHERE conrelid = 'ds_retail_customers'::regclass"
    )
    print("constraints:", [(x["conname"], x["contype"]) for x in r2.rows])
    await pool.disconnect()


if __name__ == "__main__":
    asyncio.run(main())