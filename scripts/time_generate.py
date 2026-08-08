"""Time a single SQL generation call on the 2.26M-row schema."""
import asyncio
import time

from app.agents.sql_agent import SQLAgent
from app.db.pool import PostgresPool

DSN = "postgresql://testuser:testpass@localhost:5432/testdb"


async def main() -> None:
    pool = PostgresPool(dsn=DSN)
    await pool.connect()
    agent = SQLAgent()
    agent.pool = pool
    agent.domain_guidance = "You are a finance analyst. Use COUNT(DISTINCT) for unique entities, NULLIF for division."

    schema = await pool.get_schema()
    print(f"schema: {len(schema.tables)} tables, {sum(len(c) for c in schema.columns.values())} cols total")
    sample = await pool.get_sample(schema.tables[0], n=5)
    print(f"sample: {len(sample)} rows, {len(sample[0]) if sample else 0} cols")

    t0 = time.monotonic()
    try:
        generated = await agent.generate(
            question="What is the average loan amount by grade?",
            schema=schema,
            sample_text=f"Sample from {schema.tables[0]}: {sample}",
        )
        elapsed = time.monotonic() - t0
        print(f"generate took {elapsed:.1f}s")
        print("SQL:", generated.sql[:200])
    except Exception as e:
        elapsed = time.monotonic() - t0
        print(f"generate FAILED after {elapsed:.1f}s: {type(e).__name__}: {str(e)[:300]}")
    finally:
        await pool.disconnect()


if __name__ == "__main__":
    asyncio.run(main())