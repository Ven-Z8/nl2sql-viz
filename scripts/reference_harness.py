"""Full reference test harness — WebSocket + answer spot-check.

Runs questions from a dataset's ladder against the live backend, then
SPOT-CHECKS the answer by re-running the SQL against Postgres and comparing
the numbers. A question only PASSES if:

1. A result event arrives (not an error)
2. The SQL is present
3. The answer has text
4. The chart hint is present with a valid kind
5. The answer's numbers match the actual data (spot-check)

Run SEQUENTIALLY — the WS server cannot handle many concurrent connections.

Usage:
    uv run python -m scripts.reference_harness [dataset_id] [n_questions] [delay_s]
    uv run python -m scripts.reference_harness olist 12 3
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from decimal import Decimal

import asyncpg
import websockets

API = "http://localhost:8000"
WS = "ws://localhost:8000/ws/query"

# Direct-connection DSN used ONLY by this harness for independent spot-checks;
# never sent through the API. Must point at the same DB the server registered.
SPOT_CHECK_DSN = (
    os.getenv("DEMO_DATABASE_URL") or os.getenv("DATABASE_URL")
    or "postgresql://testuser:testpass@localhost:5432/testdb"
)


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def get_demo_session() -> tuple[str, str]:
    """Return (api_key, connection_id) — the server keeps the DSN itself."""
    req = urllib.request.Request(f"{API}/api/demo/session", method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.loads(r.read().decode())
    return body["api_key"], body["connection_id"]


def load_dataset(api_key: str, dataset_id: str) -> dict:
    data = urllib.parse.urlencode({"api_key": api_key}).encode()
    req = urllib.request.Request(
        f"{API}/api/datasets/{dataset_id}/load", data=data, method="POST"
    )
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode())


# ---------------------------------------------------------------------------
# Spot-check: re-run the SQL and verify the answer's numbers
# ---------------------------------------------------------------------------

def _is_num(v) -> bool:
    return isinstance(v, (int, float, Decimal)) and not isinstance(v, bool)


async def spot_check(dsn: str, sql: str, result: dict) -> list[str]:
    """Re-run the SQL against Postgres and verify the answer's metrics.

    Returns a list of issues (empty = numbers match the data).
    """
    issues: list[str] = []
    if not sql:
        return ["no SQL to spot-check"]
    try:
        conn = await asyncpg.connect(dsn, timeout=30)
    except Exception as e:  # noqa: BLE001
        return [f"spot-check connect failed: {e}"]
    try:
        rows = await conn.fetch(sql)
    except Exception as e:  # noqa: BLE001
        return [f"spot-check re-run failed: {type(e).__name__}: {str(e)[:150]}"]
    finally:
        await conn.close()

    # Row count consistency
    reported = result.get("row_count")
    if reported is not None and len(rows) != reported:
        issues.append(f"row count: result={reported} actual={len(rows)}")

    # Metric value consistency — mirrors the backend's extract_metrics:
    # "total <col>" -> sum, "latest <col>" -> last row, plain aggregate col
    # (avg/rate/ratio/pct/median/mean prefix) -> mean, plain col -> first row
    AGG_PREFIXES = ("avg", "average", "mean", "count", "rate", "ratio",
                    "pct", "percent", "share", "sum", "total", "median")
    for m in result.get("answer", {}).get("metrics", []):
        label = m.get("label", "")
        value = m.get("value")
        if value is None:
            continue
        col = label
        kind = "plain"
        if label.startswith("total "):
            col, kind = label[6:], "total"
        elif label.startswith("latest "):
            col, kind = label[7:], "latest"
        col = re.sub(r" \(\d+\)$", "", col)  # strip dedup suffix
        if not rows or col not in rows[0]:
            continue  # column not in data — cannot check
        nums = [r[col] for r in rows if _is_num(r[col])]
        if not nums:
            continue
        if kind == "total":
            actual = sum(nums)
        elif kind == "latest":
            actual = rows[-1][col]
        elif col.lower().startswith(AGG_PREFIXES):
            actual = sum(nums) / len(nums)
        else:
            actual = rows[0][col]
        if not _is_num(actual):
            continue
        actual_f, value_f = float(actual), float(value)
        # tolerance: 1 unit or 1% — catches wrong numbers, ignores float noise
        if abs(actual_f - value_f) > max(1.0, abs(value_f) * 0.01):
            issues.append(f"metric '{label}': answer={value_f:,.2f} actual={actual_f:,.2f}")
    return issues


# ---------------------------------------------------------------------------
# Judge
# ---------------------------------------------------------------------------

def judge(question: str, tier: str, events: list[dict], spot_issues: list[str]) -> dict:
    reasons: list[str] = []
    result = next((e for e in events if e["type"] == "result"), None)
    error = next((e for e in events if e["type"] == "error"), None)
    if error:
        return {"pass": False, "reason": f"error: {error.get('message', '')[:200]}"}
    if result is None:
        return {"pass": False, "reason": "no result event"}
    if not result.get("sql"):
        reasons.append("no SQL")
    answer = result.get("answer", {})
    if not answer.get("text"):
        reasons.append("no answer")
    hint = result.get("chart_hint")
    if not isinstance(hint, dict) or not hint.get("kind"):
        reasons.append("no chart hint")
    elif hint.get("kind") not in (
        "bar", "stacked_bar", "grouped_bar", "line", "area",
        "pie", "scatter", "histogram", "kpi",
    ):
        reasons.append(f"invalid chart kind: {hint.get('kind')}")
    if spot_issues:
        reasons.append("spot-check: " + "; ".join(spot_issues[:3]))
    return {
        "pass": len(reasons) == 0,
        "reason": "; ".join(reasons) if reasons else "OK",
        "query_type": result.get("query_type"),
        "answer": answer.get("text", "")[:140],
        "sql": result.get("sql", "")[:140],
        "row_count": result.get("row_count"),
        "chart_kind": hint.get("kind") if isinstance(hint, dict) else None,
    }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

async def run_question(api_key: str, connection_id: str, question: str) -> tuple[list[dict], dict]:
    # ping_timeout=None: long LLM generation must not trip the client's
    # default 20s keepalive ping timeout (BUG-4)
    async with websockets.connect(WS, open_timeout=30, ping_interval=None, ping_timeout=None) as ws:
        await ws.send(json.dumps({"type": "auth", "api_key": api_key}))
        auth = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
        if auth.get("type") != "authenticated":
            return [], {"type": "error", "message": f"auth failed: {auth}"}
        await ws.send(json.dumps({
            "type": "query", "query": question, "connection_id": connection_id,
        }))
        events: list[dict] = []
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=600)
            ev = json.loads(raw)
            events.append(ev)
            if ev["type"] in ("result", "error"):
                break
    return events, events[-1]


async def main() -> None:
    dataset_id = sys.argv[1] if len(sys.argv) > 1 else "olist"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    delay = float(sys.argv[3]) if len(sys.argv) > 3 else 3.0

    api_key, connection_id = get_demo_session()
    print(f"demo session: {api_key[:8]}... connection_id={connection_id}")
    body = load_dataset(api_key, dataset_id)
    print(f"loaded {body['name']} — {len(body['tables'])} tables")
    questions = [
        (tier, q)
        for tier in ("easy", "medium", "hard", "very_complex")
        for q in body["questions"].get(tier, [])
    ][:limit]

    results: list[dict] = []
    for i, (tier, q) in enumerate(questions, 1):
        print(f"\n[{i}/{len(questions)}] [{tier}] {q[:70]}")
        t0 = time.monotonic()
        try:
            events, last = await run_question(api_key, connection_id, q)
            spot_issues: list[str] = []
            if last.get("type") == "result":
                spot_issues = await spot_check(SPOT_CHECK_DSN, last.get("sql", ""), last)
            j = judge(q, tier, events, spot_issues)
            j["time_s"] = round(time.monotonic() - t0, 1)
            results.append(j)
            print(f"  -> {'PASS' if j['pass'] else 'FAIL'} ({j['time_s']}s) {j.get('reason','')}")
            if j.get("query_type"):
                print(f"     type={j['query_type']} rows={j.get('row_count')} chart={j.get('chart_kind')}")
                print(f"     answer: {j.get('answer','')}")
        except Exception as e:  # noqa: BLE001
            print(f"  -> HARNESS ERROR: {type(e).__name__}: {str(e)[:200]}")
            results.append({"pass": False, "reason": f"harness: {type(e).__name__}: {str(e)[:150]}"})
        await asyncio.sleep(delay)

    # Summary
    passed = sum(1 for r in results if r["pass"])
    print(f"\n{'='*60}")
    print(f"SUMMARY: {passed}/{len(results)} passed")
    for r in results:
        print(f"  {'PASS' if r['pass'] else 'FAIL'} | {r.get('reason','')[:90]}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())