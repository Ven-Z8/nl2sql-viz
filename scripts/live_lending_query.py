"""Query-only test against the already-loaded 2.26M-row table."""
import asyncio
import json
import sys
import time
import uuid

import httpx
import websockets

API_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws/query"
DSN = "postgresql://testuser:testpass@localhost:5432/testdb"


async def main() -> int:
    async with httpx.AsyncClient(base_url=API_URL, timeout=60) as client:
        username = f"q_{uuid.uuid4().hex[:8]}"
        resp = await client.post("/api/register", json={"username": username})
        api_key = resp.json()["api_key"]

        conn = await client.post("/api/connections", json={"api_key": api_key, "dsn": DSN})
        connection_id = conn.json()["connection_id"]

    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({"type": "auth", "api_key": api_key}))
        await ws.recv()
        t0 = time.monotonic()
        await ws.send(json.dumps({
            "type": "query",
            "query": "What is the average loan amount by grade?",
            "connection_id": connection_id,
            "domain": "finance",
            "focus_table": "upload_finance_lending",
        }))
        while True:
            evt = json.loads(await asyncio.wait_for(ws.recv(), timeout=150))
            if evt["type"] in ("result", "error"):
                break
        elapsed = time.monotonic() - t0

    if evt["type"] == "error":
        print(f"FAIL ({elapsed:.1f}s): {evt['message']}")
        return 1
    print(f"query in {elapsed:.1f}s")
    print("  query_type:", evt["query_type"])
    print("  answer:", evt["answer"]["text"][:150])
    print("  rows:", evt["row_count"])
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))