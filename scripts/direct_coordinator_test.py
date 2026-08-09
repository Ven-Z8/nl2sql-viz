"""Run the coordinator directly on the 2.26M table with the fast model."""
import asyncio
import time

from app.agents.coordinator import CoordinatorAgent
from app.agents.schema_agent import SchemaAgent
from app.agents.sql_agent import SQLAgent
from app.agents.viz_agent import VizAgent
from app.db.pool import PostgresPool
from app.engine.cache import QueryCache

DSN = "postgresql://testuser:testpass@localhost:5432/testdb"


async def main() -> None:
    pool = PostgresPool(dsn=DSN)
    await pool.connect()

    schema_agent = SchemaAgent()
    schema_agent.pool = pool
    sql_agent = SQLAgent()
    sql_agent.pool = pool
    viz_agent = VizAgent()
    coordinator = CoordinatorAgent()
    coordinator.schema_agent = schema_agent
    coordinator.sql_agent = sql_agent
    coordinator.viz_agent = viz_agent
    coordinator.cache = QueryCache()
    coordinator.connection_id = "direct"
    coordinator.focus_table = "upload_finance_lending"

    t0 = time.monotonic()
    events = []
    async for evt in coordinator.run("What is the average loan amount by grade?"):
        events.append(evt)
        if evt["type"] in ("progress", "sql"):
            print(f"  [{time.monotonic()-t0:.1f}s] {evt['type']}: {str(evt.get('message') or evt.get('sql', ''))[:60]}")
        if evt["type"] in ("result", "error"):
            break
    elapsed = time.monotonic() - t0
    print(f"total: {elapsed:.1f}s")
    last = events[-1]
    if last["type"] == "error":
        print("ERROR:", last["message"])
    else:
        print("answer:", last["answer"]["text"][:120])
    await pool.disconnect()


if __name__ == "__main__":
    asyncio.run(main())