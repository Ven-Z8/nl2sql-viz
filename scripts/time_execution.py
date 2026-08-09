"""Time the actual query execution on the 2.26M table."""
import asyncio
import time

from app.db.pool import PostgresPool

DSN = "postgresql://testuser:testpass@localhost:5432/testdb"


async def main() -> None:
    pool = PostgresPool(dsn=DSN)
    await pool.connect()
    t0 = time.monotonic()
    r = await pool.execute(
        "SELECT grade, AVG(loan_amnt) AS avg_loan_amount FROM upload_finance_lending "
        "WHERE loan_amnt IS NOT NULL AND grade IS NOT NULL GROUP BY grade ORDER BY grade"
    )
    print(f"executed in {time.monotonic()-t0:.1f}s, {r.row_count} rows")
    await pool.disconnect()


if __name__ == "__main__":
    asyncio.run(main())