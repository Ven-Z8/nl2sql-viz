"""Full health check: every endpoint + the complete user flow."""
import asyncio
import json
import sys
import uuid

import httpx
import websockets

API_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws/query"
DSN = "postgresql://testuser:testpass@localhost:5432/testdb"

FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    status = "OK " if ok else "FAIL"
    print(f"  [{status}] {label}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(label)


async def main() -> int:
    async with httpx.AsyncClient(base_url=API_URL, timeout=120) as client:
        # 1. Demo questions
        r = await client.get("/api/demo/questions")
        check("GET /api/demo/questions", r.status_code == 200)

        # 2. Domains
        r = await client.get("/api/domains")
        domains = r.json().get("domains", []) if r.status_code == 200 else []
        check("GET /api/domains", r.status_code == 200 and len(domains) >= 7,
              f"{len(domains)} domains")

        # 3. Samples
        r = await client.get("/api/samples")
        samples = r.json().get("samples", []) if r.status_code == 200 else []
        check("GET /api/samples", r.status_code == 200 and len(samples) >= 1,
              f"{len(samples)} samples")

        # 4. Register
        username = f"hc_{uuid.uuid4().hex[:8]}"
        r = await client.post("/api/register", json={"username": username})
        api_key = r.json().get("api_key", "") if r.status_code == 200 else ""
        check("POST /api/register", r.status_code == 200 and api_key)

        # 5. Demo session
        r = await client.post("/api/demo/session")
        check("POST /api/demo/session", r.status_code == 200)

        # 6. Load sample
        r = await client.post("/api/samples/retail_orders/load",
                              data={"api_key": api_key})
        up = r.json() if r.status_code == 200 else {}
        check("POST /api/samples/retail_orders/load",
              r.status_code == 200 and up.get("row_count", 0) == 2000,
              f"rows={up.get('row_count')}")

        # 7. Upload CSV
        with open("scripts/test_orders.csv", "rb") as f:
            r = await client.post("/api/upload",
                                  data={"api_key": api_key, "domain": "retail"},
                                  files={"file": ("orders.csv", f, "text/csv")})
        check("POST /api/upload", r.status_code == 200 and r.json().get("row_count") == 10)

        # 8. Bad auth rejected
        r = await client.post("/api/upload",
                              data={"api_key": "bad-key", "domain": "retail"},
                              files={"file": ("x.csv", b"a,b\n1,2\n", "text/csv")})
        check("upload rejects bad key", r.status_code == 401)

    # 9. WebSocket query on the sample
    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({"type": "auth", "api_key": api_key}))
        auth = json.loads(await ws.recv())
        check("ws auth", auth.get("type") == "authenticated")

        await ws.send(json.dumps({
            "type": "query",
            "query": "What is the total revenue by region?",
            "dsn": up.get("dsn", DSN),
            "domain": "retail",
        }))
        while True:
            evt = json.loads(await asyncio.wait_for(ws.recv(), timeout=90))
            if evt["type"] in ("result", "error"):
                break
        check("ws query → result", evt["type"] == "result" and "answer" in evt,
              evt.get("message", "") if evt["type"] == "error" else "")
        if evt["type"] == "result":
            print(f"      answer: {evt['answer']['text']}")

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} checks — {', '.join(FAILURES)}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))