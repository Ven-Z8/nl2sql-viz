"""Test the SchemaLinker agent against the retail DB (coordinator flow)."""
import asyncio
import time

from app.agents.schema_agent import SchemaAgent
from app.agents.schema_linker import SchemaLinker
from app.db.pool import PostgresPool

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
    full_schema = await schema_agent.fetch_schema()
    print("full schema tables:", len(full_schema.tables))

    # Coordinator flow: scope to the focus table's FK-connected dataset
    focus_table = "ds_retail_orders"
    scope = full_schema.connected(focus_table)
    schema = full_schema.subschema(scope, first=focus_table)
    print(f"dataset schema tables ({len(schema.tables)}): {schema.tables}")
    print(f"dataset schema repr length: {len(schema.compact_repr())}")

    linker = SchemaLinker()
    t0 = time.monotonic()
    try:
        linked = await linker.link(QUESTION, schema.compact_repr())
        print(f"linker took {time.monotonic()-t0:.1f}s")
        for lt in linked:
            print(f"  {lt.table}: {lt.columns}")
        filtered = schema.filter_to(linked)
        print("filtered tables:", filtered.tables)
        print("filtered repr length:", len(filtered.compact_repr()))
    except Exception as e:
        print(f"LINKER FAILED: {type(e).__name__}: {str(e)[:800]}")
    await pool.disconnect()


if __name__ == "__main__":
    asyncio.run(main())