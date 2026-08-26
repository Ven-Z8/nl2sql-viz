"""Very-complex benchmark — 10 multi-part analytical questions across 10 databases.

Runs the fixed very_complex pick per dataset against the live backend
(:8000), then SPOT-CHECKS every answer by re-running the returned SQL against
Postgres and comparing numbers (scripts.reference_harness.judge / spot_check).

Usage:
    uv run python -m scripts.benchmark_very_complex [--all | --datasets olist,tpcds,...] [--json out.json]

    --all              run every pick (default when neither flag is given)
    --datasets a,b,c   run only the named datasets (must be known picks)
    --json PATH        incremental results file (written after each run;
                       default .scratch/benchmark_very_complex.json)
    --load             POST each dataset's /load endpoint before querying
                       (skip if the server already has the datasets loaded)

Run SEQUENTIALLY — the WS server cannot handle many concurrent connections.
The backend must already be running on :8000 with the demo session available.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.reference_harness import get_demo_session, judge, load_dataset, spot_check  # noqa: E402

import websockets  # noqa: E402

API = "http://localhost:8000"
WS = "ws://localhost:8000/ws/query"
DEFAULT_OUT = Path(".scratch") / "benchmark_very_complex.json"

# The canonical 10 picks — one very_complex question per database.
PICKS: list[tuple[str, str]] = [
    ("olist",      "Compare 2017 vs 2018 growth by product category: which categories gained share, which lost it, and what drove the shift?"),
    ("tpcds",      "Compare store vs web sales: how do the revenue trends differ over time, which categories drive the difference, and what is the return impact?"),
    ("worldbank",  "Compare the development gap: how do life expectancy, internet usage, and fossil fuel consumption differ between income groups, and which gap has widened over time?"),
    ("fdic",       "Analyze banking concentration: how much of industry assets do the top 10 banks hold, how has that share changed over time, and which regions are most concentrated?"),
    ("ga",         "Compare member vs casual rider behavior: how do trip duration and peak usage hours differ, and which station areas show the biggest seasonal swings?"),
    ("cms",        "Analyze high-cost patients: which beneficiaries accumulate the most Medicare spend, what are their common diagnoses, and how does their length of stay compare to the average?"),
    ("census",     "Compare the wealthiest vs poorest counties: how do employment, education, and commute patterns differ between them, and which states host both?"),
    ("retail",     "Analyze customer retention: what share of customers return for a second purchase, how does retention vary by segment, and which segment retains best?"),
    ("healthcare", "Analyze readmission patterns: which departments have the highest return rates, how does severity affect readmission, and what is the cost impact?"),
    ("finance",    "Analyze loan risk: how does the default rate vary by segment and region, which segments are riskiest, and how do riskier loans compare on interest rate?"),
]


async def timed_run(api_key: str, connection_id: str, question: str):
    """Run one question over WS; return (events, last_event, stage_timeline)."""
    stages: list[tuple[str, float]] = []
    t0 = time.monotonic()
    # ping timeouts disabled — long LLM generation must not trip keepalive (BUG-4)
    async with websockets.connect(WS, open_timeout=30, ping_interval=None,
                                  ping_timeout=None) as ws:
        await ws.send(json.dumps({"type": "auth", "api_key": api_key}))
        auth = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
        if auth.get("type") != "authenticated":
            return [], {"type": "error", "message": "auth failed"}, stages
        await ws.send(json.dumps({
            "type": "query", "query": question, "connection_id": connection_id,
        }))
        events: list[dict] = []
        while True:
            ev = json.loads(await asyncio.wait_for(ws.recv(), timeout=420))
            if ev["type"] == "progress":
                stages.append((ev.get("stage") or ev.get("message", "?"),
                               round(time.monotonic() - t0, 1)))
            events.append(ev)
            if ev["type"] in ("result", "error"):
                break
    total = round(time.monotonic() - t0, 1)
    return events, events[-1], stages + [("DONE", total)]


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    known = ",".join(ds for ds, _ in PICKS)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true",
                       help=f"run all {len(PICKS)} picks (default)")
    group.add_argument("--datasets", type=str, default="",
                       help=f"comma-separated subset of: {known}")
    parser.add_argument("--json", type=str, default=str(DEFAULT_OUT),
                        help=f"incremental JSON output path (default {DEFAULT_OUT})")
    parser.add_argument("--load", action="store_true",
                        help="POST /api/datasets/<id>/load before each run")
    args = parser.parse_args(argv)

    selected = [(ds, q) for ds, q in PICKS]
    if args.datasets:
        wanted = [d.strip() for d in args.datasets.split(",") if d.strip()]
        unknown = [d for d in wanted if d not in {ds for ds, _ in PICKS}]
        if unknown:
            parser.error(f"unknown dataset(s): {', '.join(unknown)} — known: {known}")
        index = {ds: q for ds, q in PICKS}
        selected = [(d, index[d]) for d in wanted]
    args.selected = selected
    return args


async def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    out_path = Path(args.json)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    api_key, demo_connection = get_demo_session()
    print(f"session ok connection_id={demo_connection}\n")

    results: list[dict] = []
    for i, (ds, q) in enumerate(args.selected, 1):
        connection_id = demo_connection
        if args.load:
            try:
                body = load_dataset(api_key, ds)
                connection_id = body.get("connection_id", demo_connection)
                print(f"[{i}/{len(args.selected)}] loaded [{ds}] — "
                      f"{len(body.get('tables', []))} tables")
            except Exception as e:  # noqa: BLE001 — record and move on
                results.append({"dataset": ds, "pass": False, "e2e_s": None,
                                "reason": f"load failed: {type(e).__name__}: {str(e)[:120]}"})
                out_path.write_text(json.dumps(results, indent=1))
                print(f"   -> LOAD ERROR {type(e).__name__}: {str(e)[:120]}")
                continue
        print(f"[{i}/{len(args.selected)}] [{ds}] {q[:72]}...")
        try:
            events, last, stages = await timed_run(api_key, connection_id, q)
            issues: list[str] = []
            if last.get("type") == "result":
                issues = await spot_check(
                    _spot_check_dsn(), last.get("sql", ""), last
                )
            j = judge(q, "very_complex", events, issues)
            j["dataset"] = ds
            j["e2e_s"] = stages[-1][1]
            j["stages"] = stages[:-1]
            result_event = next((e for e in events if e.get("type") == "result"), None)
            if result_event:
                j["queries"] = result_event.get("queries", [])
                j["provenance_count"] = len(result_event.get("provenance") or [])
            results.append(j)
            mark = "PASS" if j["pass"] else f"FAIL ({j.get('reason', '')[:80]})"
            print(f"   -> {mark} | e2e={j['e2e_s']}s rows={j.get('row_count')} "
                  f"chart={j.get('chart_kind')}")
            if not j["pass"]:
                print(f"     answer: {str(j.get('answer', ''))[:120]}")
        except Exception as e:  # noqa: BLE001 — harness errors are data too
            results.append({"dataset": ds, "pass": False, "e2e_s": None,
                            "reason": f"harness {type(e).__name__}: {str(e)[:120]}"})
            print(f"   -> ERROR {type(e).__name__}: {str(e)[:120]}")
        out_path.write_text(json.dumps(results, indent=1))
        await asyncio.sleep(2)

    ok = [r for r in results if r["pass"]]
    times = sorted(r["e2e_s"] for r in ok if r["e2e_s"] is not None)
    print("\n" + "=" * 62)
    print(f"BENCHMARK: {len(ok)}/{len(results)} passed | grounded spot-checks incl.")
    if times:
        print(f"E2E seconds — min {times[0]} · median {times[len(times)//2]} · max {times[-1]}")
    print(f"Results written incrementally to {out_path}")


def _spot_check_dsn() -> str:
    """Direct DSN for independent spot-checks — parsed like reference_harness."""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    fallback = "postgresql://testuser:testpass@localhost:5432/testdb"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("DEMO_DATABASE_URL="):
                return line.split("=", 1)[1].strip()
            if line.startswith("DATABASE_URL="):
                return line.split("=", 1)[1].strip()
    return fallback


if __name__ == "__main__":
    asyncio.run(main())
