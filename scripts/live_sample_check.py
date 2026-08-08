"""Live test: load the bundled retail sample and query it."""
import asyncio
import json
import sys
import uuid

import httpx
import websockets

API_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws/query"


async def main() -> int:
    async with httpx.AsyncClient(base_url=API_URL, timeout=120) as client:
        username = f"smp_{uuid.uuid4().hex[:8]}"
        resp = await client.post("/api/register", json={"username": username})
        api_key = resp.json()["api_key"]

        samples = await client.get("/api/samples")
        print("samples:", [(s["id"], s["domain"]) for s in samples.json()["samples"]])

        load = await client.post(
            "/api/samples/retail_orders/load",
            data={"api_key": api_key},
        )
        if load.status_code != 200:
            print("FAIL load:", load.status_code, load.text)
            return 1
        up = load.json()
        print("loaded:", up["table_name"], "rows:", up["row_count"], "domain:", up["domain"])
        print("  columns:", up["columns"])

    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({"type": "auth", "api_key": api_key}))
        await ws.recv()
        await ws.send(json.dumps({
            "type": "query",
            "query": "What is the average order value by category?",
            "dsn": up["dsn"],
            "domain": "retail",
        }))
        while True:
            evt = json.loads(await asyncio.wait_for(ws.recv(), timeout=90))
            if evt["type"] in ("result", "error"):
                break

    if evt["type"] == "error":
        print("FAIL:", evt["message"])
        return 1
    print("query_type:", evt["query_type"])
    print("answer:", evt["answer"]["text"])
    print("rows:", evt["row_count"])
    print("PASS: sample load + query OK")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))