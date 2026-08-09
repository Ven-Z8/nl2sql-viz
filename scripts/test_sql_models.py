"""Test which fast model produces usable SQL via the NOOA client."""
import asyncio

from nooa.unifiedllm.registry import get_llm_client

MODELS = [
    "openrouter/google/gemini-3.6-flash",
    "openrouter/qwen/qwen3.7-flash",
    "openrouter/deepseek/deepseek-v4-flash-0731",
    "openrouter/inclusionai/ling-3.0-flash",
]

PROMPT = (
    "Return a JSON object with keys sql and explanation. "
    "sql: SELECT grade, AVG(loan_amnt) AS avg_loan_amount FROM upload_finance_lending "
    "GROUP BY grade ORDER BY grade. explanation: Average loan amount per grade."
)


async def test(model: str) -> None:
    try:
        c = get_llm_client(model)
        r = await c.acall(messages=[{"role": "user", "content": PROMPT}], max_tokens=200)
        text = str(r.raw_response.choices[0].message.content or "")[:80]
        print(f"{model}: content={text!r}")
    except Exception as e:
        print(f"{model}: FAIL {str(e)[:100]}")


async def main() -> None:
    for m in MODELS:
        await test(m)


if __name__ == "__main__":
    asyncio.run(main())