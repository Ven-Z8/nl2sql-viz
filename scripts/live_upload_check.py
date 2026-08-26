"""Live test: register -> upload CSV -> query the uploaded table with a domain skill."""
import asyncio
import json
import sys
import uuid

import httpx
import websockets

API_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws/query"
CSV_PATH = "scripts/test_orders.csv"


async def main() -> int:
    async with httpx.AsyncClient(base_url=API_URL, timeout=60) as client:
        username = f"up_{uuid.uuid4().hex[:8]}"
        resp = await client.post("/api/register", json={"username": username})
        api_key = resp.json()["api_key"]
        print("registered:", username)

        domains = await client.get("/api/domains")
        print("domains:", [d["id"] for d in domains.json()["domains"]])

        with open(CSV_PATH, "rb") as f:
            upload = await client.post(
                "/api/upload",
                data={"api_key": api_key, "domain": "retail"},
                files={"file": ("orders.csv", f, "text/csv")},
            )
        if upload.status_code != 200:
            print("FAIL upload:", upload.status_code, upload.text)
            return 1
        up = upload.json()
        print("uploaded:", up["table_name"], "rows:", up["row_count"])
        print("  columns:", up["columns"])
        print("  types:", up["types"])

    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({"type": "auth", "api_key": api_key}))
        await ws.recv()
        await ws.send(json.dumps({
            "type": "query",
            "query": "What is the total revenue by region, excluding refunded orders?",
            "connection_id": up["connection_id"],
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
    print("PASS: upload + domain-skilled query OK")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))