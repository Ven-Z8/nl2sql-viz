"""Live test: load the real datasets (bankruptcy 96 cols, online retail 542K rows) and query."""
import asyncio
import json
import sys
import time
import uuid

import httpx
import websockets

API_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws/query"


async def load_and_query(client, api_key, sample_id, question) -> bool:
    t0 = time.monotonic()
    load = await client.post(f"/api/samples/{sample_id}/load", data={"api_key": api_key})
    elapsed = time.monotonic() - t0
    if load.status_code != 200:
        print(f"  FAIL load {sample_id}: {load.status_code} {load.text[:200]}")
        return False
    up = load.json()
    print(f"  loaded {sample_id}: {up['row_count']:,} rows, {len(up['columns'])} cols in {elapsed:.1f}s")
    print(f"    questions: {len(up.get('questions', []))}")

    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({"type": "auth", "api_key": api_key}))
        await ws.recv()
        await ws.send(json.dumps({
            "type": "query", "query": question,
            "connection_id": up["connection_id"], "domain": up["domain"],
        }))
        while True:
            evt = json.loads(await asyncio.wait_for(ws.recv(), timeout=120))
            if evt["type"] in ("result", "error"):
                break
    if evt["type"] == "error":
        print(f"  FAIL query: {evt['message']}")
        return False
    print(f"    query_type={evt['query_type']} answer={evt['answer']['text'][:80]}")
    return True


async def main() -> int:
    async with httpx.AsyncClient(base_url=API_URL, timeout=300) as client:
        username = f"real_{uuid.uuid4().hex[:8]}"
        resp = await client.post("/api/register", json={"username": username})
        api_key = resp.json()["api_key"]

        ok = True
        ok &= await load_and_query(
            client, api_key, "finance_bankruptcy",
            "What is the average debt ratio by bankruptcy status?",
        )
        ok &= await load_and_query(
            client, api_key, "marketing_shoppers",
            "What is the conversion rate by visitor type?",
        )
        ok &= await load_and_query(
            client, api_key, "retail_online",
            "What is the total revenue by country?",
        )

    print("PASS: real datasets OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))