"""Test creating a table with PK via execute_raw."""
import asyncio

from app.db.pool import PostgresPool

DSN = "postgresql://testuser:testpass@localhost:5432/testdb"


async def main() -> None:
    pool = PostgresPool(dsn=DSN)
    await pool.connect()
    await pool.execute_raw('DROP TABLE IF EXISTS "test_pk" CASCADE')
    await pool.execute_raw('CREATE TABLE "test_pk" ("id" TEXT PRIMARY KEY, "name" TEXT)')
    r = await pool.execute(
        "SELECT conname, contype FROM pg_constraint WHERE conrelid = 'test_pk'::regclass"
    )
    print("constraints:", [(x["conname"], x["contype"]) for x in r.rows])
    await pool.execute_raw('DROP TABLE IF EXISTS "test_pk" CASCADE')
    await pool.disconnect()


if __name__ == "__main__":
    asyncio.run(main())