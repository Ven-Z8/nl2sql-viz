"""Live stress test: load the 2.26M-row Lending Club dataset and query it."""
import asyncio
import json
import sys
import time
import uuid

import httpx
import websockets

API_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws/query"


async def main() -> int:
    async with httpx.AsyncClient(base_url=API_URL, timeout=600) as client:
        username = f"big_{uuid.uuid4().hex[:8]}"
        resp = await client.post("/api/register", json={"username": username})
        api_key = resp.json()["api_key"]

        t0 = time.monotonic()
        load = await client.post(
            "/api/samples/finance_lending/load", data={"api_key": api_key}
        )
        load_elapsed = time.monotonic() - t0
        if load.status_code != 200:
            print("FAIL load:", load.status_code, load.text[:300])
            return 1
        up = load.json()
        print(f"loaded {up['row_count']:,} rows, {len(up['columns'])} cols in {load_elapsed:.1f}s")
        print(f"  questions: {len(up.get('questions', []))}")

    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({"type": "auth", "api_key": api_key}))
        await ws.recv()
        t0 = time.monotonic()
        await ws.send(json.dumps({
            "type": "query",
            "query": "What is the average loan amount by grade?",
            "connection_id": up["connection_id"],
            "domain": "finance",
        }))
        while True:
            evt = json.loads(await asyncio.wait_for(ws.recv(), timeout=180))
            if evt["type"] in ("result", "error"):
                break
        query_elapsed = time.monotonic() - t0

    if evt["type"] == "error":
        print(f"FAIL query ({query_elapsed:.1f}s): {evt['message']}")
        return 1
    print(f"query in {query_elapsed:.1f}s")
    print("  query_type:", evt["query_type"])
    print("  answer:", evt["answer"]["text"][:120])
    print("  rows:", evt["row_count"])
    print("PASS: 2.26M-row dataset OK")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))