"""Live E2E check: register -> auth -> query -> result with chart_spec."""
import asyncio
import json
import sys
import uuid

import httpx
import websockets

API_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws/query"
DSN = "postgresql://testuser:testpass@localhost:5432/testdb"


async def main() -> int:
    async with httpx.AsyncClient(base_url=API_URL) as client:
        username = f"live_{uuid.uuid4().hex[:8]}"
        resp = await client.post("/api/register", json={"username": username})
        if resp.status_code != 200:
            print(f"FAIL register: {resp.status_code} {resp.text}")
            return 1
        api_key = resp.json()["api_key"]
        print("registered:", username)

        questions = await client.get("/api/demo/questions")
        print("demo/questions:", questions.status_code, "OK" if questions.status_code == 200 else questions.text)
        if questions.status_code == 200:
            qs = questions.json()["questions"]
            print(f"  {len(qs)} suggested questions")

        # Register the demo DB server-side; only the id goes over the wire
        conn = await client.post("/api/connections", json={"api_key": api_key, "dsn": DSN})
        if conn.status_code != 200:
            print(f"FAIL connect: {conn.status_code} {conn.text}")
            return 1
        connection_id = conn.json()["connection_id"]

    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({"type": "auth", "api_key": api_key}))
        auth = json.loads(await ws.recv())
        assert auth["type"] == "authenticated", f"auth failed: {auth}"
        print("authenticated:", auth["user_id"])

        await ws.send(json.dumps({
            "type": "query",
            "query": "Show monthly recurring revenue by plan tier over time",
            "connection_id": connection_id,
        }))

        events = []
        while True:
            try:
                evt = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
            except asyncio.TimeoutError:
                print("FAIL: timed out waiting for result")
                return 1
            events.append(evt)
            if evt["type"] in ("result", "error"):
                break

        for evt in events:
            if evt["type"] == "progress":
                print("  progress:", evt.get("message"))
            elif evt["type"] == "sql":
                print("  sql:", evt["sql"][:80])

        result = events[-1]
        if result["type"] == "error":
            print("FAIL: error event:", result["message"])
            return 1

        print("result event keys:", sorted(result.keys()))
        chart_hint = result.get("chart_hint")
        if not isinstance(chart_hint, dict) or not chart_hint.get("kind"):
            print("FAIL: no chart_hint.kind in result")
            return 1
        print("  row_count:", result.get("row_count"))
        print("  chart kind:", chart_hint.get("kind"), "x:", chart_hint.get("x"), "y:", chart_hint.get("y"))
        answer = result.get("answer")
        if not answer or not answer.get("text"):
            print("FAIL: no grounded answer in result")
            return 1
        print("  query_type:", answer.get("query_type"))
        print("  answer:", answer["text"])
        print("  metrics:", [(m["label"], m["value"]) for m in answer.get("metrics", [])])
        print("  cached:", result.get("cached"))
        print("PASS: live E2E OK")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
