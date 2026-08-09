"""Test the schema validator on the failing query."""
import asyncio

from app.core.schema_validator import SchemaValidator
from app.db.pool import PostgresPool

DSN = "postgresql://testuser:testpass@localhost:5432/testdb"

BAD_SQL = """
SELECT c.state AS region, COUNT(DISTINCT o.order_id) AS orders
FROM ds_retail_orders o
JOIN ds_retail_customers c ON c.customer_id = o.customer_id
GROUP BY c.state
"""


async def main() -> None:
    pool = PostgresPool(dsn=DSN)
    await pool.connect()
    schema = await pool.get_schema()
    validator = SchemaValidator(schema)  # full schema — joins need all tables' columns

    ok, fixed, errors = validator.validate_and_fix(BAD_SQL)
    print("ok:", ok)
    print("errors:", errors)
    print("fixed SQL:", fixed[:200])
    await pool.disconnect()


if __name__ == "__main__":
    asyncio.run(main())