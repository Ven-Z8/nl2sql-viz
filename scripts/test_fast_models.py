"""Test fast OpenRouter models for speed."""
import asyncio
import time

import litellm

MODELS = [
    "openrouter/google/gemini-3.6-flash",
    "openrouter/qwen/qwen3.7-flash",
    "openrouter/deepseek/deepseek-v4-flash-0731",
    "openrouter/inclusionai/ling-3.0-flash",
]


async def test(model: str) -> None:
    try:
        t0 = time.monotonic()
        r = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": "Say hi in 3 words"}],
            max_tokens=20,
        )
        content = r.choices[0].message.content or ""
        print(f"{model}: {time.monotonic()-t0:.1f}s -> {content[:40]!r}")
    except Exception as e:
        print(f"{model}: FAIL {str(e)[:100]}")


async def main() -> None:
    for m in MODELS:
        await test(m)


if __name__ == "__main__":
    asyncio.run(main())