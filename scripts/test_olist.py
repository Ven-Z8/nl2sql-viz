"""Run Olist questions through the coordinator (easy + very-complex)."""
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

QUESTIONS = [
    "What is the total revenue from all orders?",
    "Compare 2017 vs 2018 revenue by product category, identify the top 3 categories driving growth, and explain what changed in the payment method mix",
]


async def run_one(pool, question: str) -> None:
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
    coordinator.connection_id = "olist"
    coordinator.focus_table = "ds_olist_orders"

    t0 = time.monotonic()
    events = []
    async for evt in coordinator.run(question):
        events.append(evt)
        if evt["type"] in ("progress", "sql"):
            print(f"  [{time.monotonic()-t0:.1f}s] {evt['type']}: {str(evt.get('message') or evt.get('sql', ''))[:90]}")
        if evt["type"] in ("result", "error"):
            break
    elapsed = time.monotonic() - t0
    print(f"  total: {elapsed:.1f}s")
    last = events[-1]
    if last["type"] == "error":
        print("  ERROR:", last["message"])
    else:
        print("  query_type:", last.get("query_type"))
        print("  answer:", last["answer"]["text"][:250])
        print("  metrics:", [(m["label"], round(m["value"], 2)) for m in last["answer"]["metrics"]][:6])
        print("  sections:", len(last["answer"].get("sections", [])))
    print()


async def main() -> None:
    pool = PostgresPool(dsn=DSN)
    await pool.connect()
    for q in QUESTIONS:
        print(f"Q: {q}")
        await run_one(pool, q)
    await pool.disconnect()


if __name__ == "__main__":
    asyncio.run(main())