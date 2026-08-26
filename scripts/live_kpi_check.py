"""Live KPI-path check: 'How many accounts?' should classify as kpi."""
import asyncio
import json
import uuid

import httpx
import websockets

DSN = "postgresql://testuser:testpass@localhost:5432/testdb"


async def main() -> int:
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        username = f"kpi_{uuid.uuid4().hex[:8]}"
        resp = await client.post("/api/register", json={"username": username})
        api_key = resp.json()["api_key"]

        # Register the local demo DB server-side; only the id goes over the wire
        conn = await client.post("/api/connections", json={"api_key": api_key, "dsn": DSN})
        connection_id = conn.json()["connection_id"]

    async with websockets.connect("ws://localhost:8000/ws/query") as ws:
        await ws.send(json.dumps({"type": "auth", "api_key": api_key}))
        await ws.recv()
        await ws.send(json.dumps({
            "type": "query",
            "query": "How many accounts are there?",
            "connection_id": connection_id,
        }))
        while True:
            evt = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
            if evt["type"] in ("result", "error"):
                break

    if evt["type"] == "error":
        print("ERROR:", evt["message"])
        return 1
    print("query_type:", evt["query_type"])
    print("answer:", evt["answer"]["text"])
    print("metrics:", [(m["label"], m["value"]) for m in evt["answer"]["metrics"]])
    if evt["query_type"] != "kpi":
        print("FAIL: expected kpi")
        return 1
    print("KPI OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))