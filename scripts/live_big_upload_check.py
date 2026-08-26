"""Live test: upload the real UCI Online Retail dataset (~542K rows) and query it."""
import asyncio
import json
import sys
import time
import uuid

import httpx
import websockets

API_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws/query"
CSV_PATH = "scripts/online_retail_ii.csv"


async def main() -> int:
    async with httpx.AsyncClient(base_url=API_URL, timeout=300) as client:
        username = f"big_{uuid.uuid4().hex[:8]}"
        resp = await client.post("/api/register", json={"username": username})
        api_key = resp.json()["api_key"]

        with open(CSV_PATH, "rb") as f:
            t0 = time.monotonic()
            upload = await client.post(
                "/api/upload",
                data={"api_key": api_key, "domain": "retail"},
                files={"file": ("online_retail.csv", f, "text/csv")},
            )
            elapsed = time.monotonic() - t0
        if upload.status_code != 200:
            print("FAIL upload:", upload.status_code, upload.text[:300])
            return 1
        up = upload.json()
        print(f"uploaded {up['row_count']:,} rows in {elapsed:.1f}s")
        print("  table:", up["table_name"])
        print("  columns:", up["columns"])
        print("  types:", up["types"])

    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({"type": "auth", "api_key": api_key}))
        await ws.recv()
        await ws.send(json.dumps({
            "type": "query",
            "query": "What is the monthly revenue trend and top 5 best-selling products by quantity?",
            "connection_id": up["connection_id"],
            "domain": "retail",
        }))
        while True:
            evt = json.loads(await asyncio.wait_for(ws.recv(), timeout=120))
            if evt["type"] in ("result", "error"):
                break

    if evt["type"] == "error":
        print("FAIL:", evt["message"])
        return 1
    print("query_type:", evt["query_type"])
    print("answer:", evt["answer"]["text"])
    print("rows:", evt["row_count"])
    print("PASS: big-dataset upload + query OK")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))