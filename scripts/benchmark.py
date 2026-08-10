"""Run one dataset's question ladder through the coordinator, recording results.

Usage: uv run python -m scripts.benchmark <dataset_id> [delay_seconds]

Writes results incrementally to data/benchmark/<dataset_id>.json so partial
progress survives. Sleeps between questions to stay under LLM rate limits.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

from app.agents.coordinator import CoordinatorAgent
from app.agents.schema_agent import SchemaAgent
from app.agents.schema_linker import SchemaLinker
from app.agents.sql_agent import SQLAgent
from app.agents.viz_agent import VizAgent
from app.db.pool import PostgresPool
from app.engine.cache import QueryCache

DSN = "postgresql://testuser:testpass@localhost:5432/testdb"
OUT_DIR = Path("data/benchmark")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Primary table per dataset — the "hub" the question ladder is written against
FOCUS = {
    "olist": "ds_olist_orders",
    "fdic": "ds_fdic_institutions",
    "ga": "ds_ga_trips",
    "census": "ds_census_tracts",
    "tpcds": "ds_tpcds_store_sales",
    "cms": "ds_cms_claims",
    "worldbank": "ds_worldbank_values",
    "retail": "ds_retail_orders",
    "healthcare": "ds_healthcare_patients",
    "finance": "ds_finance_loans",
    "demographics_census": "ds_demographics_census_households",
    "demographics_consumer": "ds_demographics_consumer_consumers",
}

TIER_ORDER = ["easy", "medium", "hard", "very_complex"]


def load_questions(dataset_id: str) -> list[tuple[str, str]]:
    path = Path("data/datasets") / dataset_id / "questions.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return [(tier, q) for tier in TIER_ORDER for q in data.get(tier, [])]


async def run_question(pool, dataset_id: str, question: str) -> dict:
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
    coordinator.connection_id = f"bench-{dataset_id}"
    coordinator.focus_table = FOCUS.get(dataset_id)

    t0 = time.monotonic()
    events = []
    try:
        async for evt in coordinator.run(question):
            events.append(evt)
            if evt["type"] in ("result", "error"):
                break
    except Exception as e:  # noqa: BLE001 — record any failure, keep going
        return {"success": False, "error": f"{type(e).__name__}: {str(e)[:300]}", "wall_time_s": round(time.monotonic() - t0, 1)}
    wall = round(time.monotonic() - t0, 1)
    last = events[-1] if events else {}
    if last.get("type") == "error":
        return {"success": False, "error": last.get("message", "unknown"), "wall_time_s": wall}
    if last.get("type") != "result":
        return {"success": False, "error": f"no result event ({last.get('type')})", "wall_time_s": wall}
    answer = last.get("answer", {})
    return {
        "success": True,
        "query_type": last.get("query_type"),
        "answer": answer.get("text", ""),
        "metrics": [(m.get("label"), round(m.get("value", 0), 2)) for m in answer.get("metrics", [])][:6],
        "sections": len(answer.get("sections", [])),
        "sql": last.get("sql", ""),
        "execution_time_ms": last.get("execution_time_ms", 0),
        "row_count": last.get("row_count", 0),
        "wall_time_s": wall,
    }


async def main() -> None:
    dataset_id = sys.argv[1]
    delay = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 0  # 0 = all
    questions = load_questions(dataset_id)
    if limit:
        questions = questions[:limit]
    out_path = OUT_DIR / f"{dataset_id}.json"
    # Resume: skip questions already recorded (benchmark is idempotent)
    done_questions = set()
    if out_path.exists():
        try:
            for r in json.loads(out_path.read_text(encoding="utf-8")):
                done_questions.add(r["question"])
        except json.JSONDecodeError:
            pass
    todo = [(t, q) for t, q in questions if q not in done_questions]
    print(f"[{dataset_id}] {len(todo)}/{len(questions)} questions to run, delay {delay}s", flush=True)

    pool = PostgresPool(dsn=DSN)
    await pool.connect()
    results: list[dict] = []
    if out_path.exists():
        try:
            results = json.loads(out_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            results = []
    for i, (tier, q) in enumerate(todo, 1):
        print(f"[{dataset_id}] {i}/{len(todo)} [{tier}] {q[:70]}", flush=True)
        t0 = time.monotonic()
        rec = await run_question(pool, dataset_id, q)
        rec.update({"dataset": dataset_id, "tier": tier, "question": q, "elapsed_s": round(time.monotonic() - t0, 1)})
        results.append(rec)
        # Incremental save — survives crashes
        out_path.write_text(json.dumps(results, indent=1), encoding="utf-8")
        status = "OK" if rec["success"] else "FAIL"
        print(f"[{dataset_id}]   -> {status} ({rec.get('wall_time_s')}s) {rec.get('answer', '')[:80]}", flush=True)
        if i < len(todo):
            await asyncio.sleep(delay)
    await pool.disconnect()
    print(f"[{dataset_id}] done: {sum(1 for r in results if r['success'])}/{len(results)} passed", flush=True)


if __name__ == "__main__":
    asyncio.run(main())