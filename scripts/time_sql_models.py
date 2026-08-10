"""Time SQL generation with different models."""
import asyncio
import time

from nooa.unifiedllm.registry import get_llm_client

MODELS = [
    "openrouter/deepseek/deepseek-v4-flash-0731",
    "openrouter/inclusionai/ling-3.0-flash",
]

PROMPT = """Return a JSON object with keys sql and explanation.
Question: What is the total revenue by region?
Schema: customers(customer_id TEXT [PK], name TEXT, segment TEXT, region TEXT, signup_date DATE)
orders(order_id TEXT [PK], customer_id TEXT [FK->customers.customer_id], order_date DATE, status TEXT, channel TEXT)
order_items(order_item_id TEXT [PK], order_id TEXT [FK->orders.order_id], product_id TEXT [FK->products.product_id], quantity BIGINT, unit_price DOUBLE PRECISION)
Sample data from customers (first 2 rows):
customer_id | name | segment | region | signup_date
C000001 | Customer 1 | Consumer | North | 2023-01-15
C000002 | Customer 2 | Corporate | South | 2023-02-01
Write SQL: total revenue (quantity * unit_price) by region for completed orders."""


async def test(model: str) -> None:
    try:
        c = get_llm_client(model)
        t0 = time.monotonic()
        r = await c.acall(messages=[{"role": "user", "content": PROMPT}], max_tokens=400)
        elapsed = time.monotonic() - t0
        text = str(r.raw_response.choices[0].message.content or "")[:100]
        print(f"{model}: {elapsed:.1f}s -> {text!r}")
    except Exception as e:
        print(f"{model}: FAIL {str(e)[:100]}")


async def main() -> None:
    for m in MODELS:
        await test(m)


if __name__ == "__main__":
    asyncio.run(main())