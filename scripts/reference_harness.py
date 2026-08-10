"""Reference test harness — correct way to test the NL2SQL app over WebSocket.

Fixes the three harness bugs the previous test run hit:
1. chart_spec is {renderer, spec, plan, row_count} — the Vega-Lite spec
   ($schema, mark, encoding) lives INSIDE chart_spec["spec"], not at the top.
2. Run questions SEQUENTIALLY with a delay — the WS server cannot handle
   134 concurrent connections (handshake timeouts).
3. Capture the real error message from the WS error event; never compute
   metrics in the harness (the backend does that).

Usage: uv run python -m scripts.reference_harness [dataset_id] [n_questions]
"""
import asyncio
import json
import sys
import time
import urllib.request

import websockets

API = "http://localhost:8000"
WS = "ws://localhost:8000/ws/query"


def get_demo_session() -> tuple[str, str]:
    req = urllib.request.Request(f"{API}/api/demo/session", method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.loads(r.read().decode())
    return body["api_key"], body["dsn"]


def load_dataset(api_key: str, dataset_id: str) -> dict:
    import urllib.parse

    data = urllib.parse.urlencode({"api_key": api_key}).encode()
    req = urllib.request.Request(f"{API}/api/datasets/{dataset_id}/load", data=data, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def judge(question: str, tier: str, events: list[dict]) -> dict:
    """Judge one question. Checks the CORRECT paths."""
    reasons: list[str] = []
    result = next((e for e in events if e["type"] == "result"), None)
    error = next((e for e in events if e["type"] == "error"), None)
    if error:
        return {"pass": False, "reason": f"error: {error.get('message', '')[:200]}"}
    if result is None:
        return {"pass": False, "reason": "no result event"}
    # SQL
    sql = result.get("sql", "")
    if not sql:
        reasons.append("no SQL")
    # Answer
    answer = result.get("answer", {})
    if not answer.get("text"):
        reasons.append("no answer")
    # Chart — the Vega-Lite spec is INSIDE chart_spec["spec"]
    chart = result.get("chart_spec", {})
    spec = chart.get("spec", {}) if isinstance(chart, dict) else {}
    if not spec.get("$schema"):
        reasons.append("no chart spec")
    if not spec.get("mark"):
        reasons.append("no chart mark")
    return {
        "pass": len(reasons) == 0,
        "reason": "; ".join(reasons) if reasons else "OK",
        "query_type": result.get("query_type"),
        "answer": answer.get("text", "")[:120],
        "sql": sql[:120],
        "chart_keys": list(spec.keys())[:6],
        "row_count": result.get("row_count"),
    }


async def run_question(api_key: str, dsn: str, question: str, tier: str) -> dict:
    async with websockets.connect(WS, open_timeout=30) as ws:
        await ws.send(json.dumps({"type": "auth", "api_key": api_key}))
        auth = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
        if auth.get("type") != "authenticated":
            return {"pass": False, "reason": f"auth failed: {auth}"}
        await ws.send(json.dumps({"type": "query", "query": question, "dsn": dsn}))
        events: list[dict] = []
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=300)
            ev = json.loads(raw)
            events.append(ev)
            if ev["type"] in ("result", "error"):
                break
    return judge(question, tier, events)


async def main() -> None:
    dataset_id = sys.argv[1] if len(sys.argv) > 1 else "olist"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    api_key, dsn = get_demo_session()
    print(f"demo session: {api_key[:8]}... dsn={dsn[:40]}...")
    body = load_dataset(api_key, dataset_id)
    print(f"loaded {body['name']} — {len(body['tables'])} tables")
    questions = [
        (tier, q)
        for tier in ("easy", "medium", "hard", "very_complex")
        for q in body["questions"].get(tier, [])
    ][:limit]

    for i, (tier, q) in enumerate(questions, 1):
        print(f"\n[{i}/{len(questions)}] [{tier}] {q[:70]}")
        t0 = time.monotonic()
        try:
            j = await run_question(api_key, dsn, q, tier)
            j["time_s"] = round(time.monotonic() - t0, 1)
            print(f"  -> {'PASS' if j['pass'] else 'FAIL'} ({j['time_s']}s) {j.get('reason','')}")
            if j.get("query_type"):
                print(f"     type={j['query_type']} rows={j.get('row_count')} chart={j.get('chart_keys')}")
                print(f"     answer: {j.get('answer','')}")
        except Exception as e:  # noqa: BLE001
            print(f"  -> HARNESS ERROR: {type(e).__name__}: {str(e)[:200]}")
        await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(main())