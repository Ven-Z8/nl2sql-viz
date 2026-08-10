"""Run a very-complex question through the coordinator on the retail DB."""
import asyncio
import time

from app.agents.coordinator import CoordinatorAgent
from app.agents.schema_agent import SchemaAgent
from app.agents.schema_linker import SchemaLinker
from app.agents.sql_agent import SQLAgent
from app.agents.viz_agent import VizAgent
from app.db.pool import PostgresPool
from app.engine.cache import QueryCache

DSN = "postgresql://testuser:testpass@localhost:5432/testdb"
QUESTION = (
    "Compare Q4 vs Q3 revenue by region, identify the top 3 growth categories, "
    "and explain the driver behind the growth"
)


async def main() -> None:
    pool = PostgresPool(dsn=DSN)
    await pool.connect()

    schema_agent = SchemaAgent()
    schema_agent.pool = pool
    sql_agent = SQLAgent()
    sql_agent.pool = pool
    viz_agent = VizAgent()
    linker = SchemaLinker()
    coordinator = CoordinatorAgent()
    coordinator.schema_agent = schema_agent
    coordinator.sql_agent = sql_agent
    coordinator.viz_agent = viz_agent
    coordinator.linker = linker
    coordinator.cache = QueryCache()
    coordinator.connection_id = "direct"
    coordinator.focus_table = "ds_retail_orders"

    t0 = time.monotonic()
    events = []
    async for evt in coordinator.run(QUESTION):
        events.append(evt)
        if evt["type"] in ("progress", "sql"):
            print(f"  [{time.monotonic()-t0:.1f}s] {evt['type']}: {str(evt.get('message') or evt.get('sql', ''))[:80]}")
        if evt["type"] in ("result", "error"):
            break
    elapsed = time.monotonic() - t0
    print(f"\ntotal: {elapsed:.1f}s")
    last = events[-1]
    if last["type"] == "error":
        print("ERROR:", last["message"])
    else:
        print("query_type:", last.get("query_type"))
        print("answer:", last["answer"]["text"][:300])
        print("metrics:", [(m["label"], m["value"]) for m in last["answer"]["metrics"]][:8])
        print("sub_queries:", [s["question"] for s in last["answer"]["sub_queries"]])
    await pool.disconnect()


if __name__ == "__main__":
    asyncio.run(main())