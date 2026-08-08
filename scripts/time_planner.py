"""Check what the planner returns for a simple query."""
import asyncio

from app.agents.planner import QueryPlanner
from app.db.pool import PostgresPool

DSN = "postgresql://testuser:testpass@localhost:5432/testdb"


async def main() -> None:
    pool = PostgresPool(dsn=DSN)
    await pool.connect()
    schema = await pool.get_schema()
    focused = schema.focused("upload_finance_lending")
    sample = await pool.get_sample("upload_finance_lending", n=5)
    sample_text = f"Sample from upload_finance_lending: {sample}"

    planner = QueryPlanner()
    t0 = asyncio.get_event_loop().time()
    try:
        subs = await planner.decompose(
            "What is the average loan amount by grade?",
            focused.compact_repr(),
            sample_text,
        )
        elapsed = asyncio.get_event_loop().time() - t0
        print(f"planner took {elapsed:.1f}s, returned {len(subs)} sub-queries")
        for s in subs:
            print("  -", s.question)
    except Exception as e:
        elapsed = asyncio.get_event_loop().time() - t0
        print(f"planner FAILED after {elapsed:.1f}s: {type(e).__name__}: {str(e)[:200]}")
    finally:
        await pool.disconnect()


if __name__ == "__main__":
    asyncio.run(main())