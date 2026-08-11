"""End-to-end test against the LIVE public endpoint."""
import asyncio
import json
import urllib.parse
import urllib.request

import websockets

API = "https://nl2sql2viz.duckdns.org"
WS = "wss://nl2sql2viz.duckdns.org/ws/query"
QUESTION = "How does order volume vary by order status?"


async def main() -> None:
    req = urllib.request.Request(f"{API}/api/demo/session", method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.loads(r.read().decode())
    api_key, dsn = body["api_key"], body["dsn"]
    print("demo session OK — dsn host:", dsn.split("@")[1].split(":")[0])

    data = urllib.parse.urlencode({"api_key": api_key}).encode()
    req = urllib.request.Request(f"{API}/api/datasets/olist/load", data=data, method="POST")
    with urllib.request.urlopen(req, timeout=600) as r:
        loaded = json.loads(r.read().decode())
    print(f"olist loaded: {loaded['name']} — {len(loaded['tables'])} tables")

    async with websockets.connect(WS, open_timeout=30, ping_interval=None, ping_timeout=None) as ws:
        await ws.send(json.dumps({"type": "auth", "api_key": api_key}))
        auth = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
        print("auth:", auth.get("type"))
        await ws.send(json.dumps({"type": "query", "query": QUESTION, "dsn": dsn}))
        while True:
            ev = json.loads(await asyncio.wait_for(ws.recv(), timeout=600))
            if ev["type"] == "progress":
                print("progress:", ev.get("message", "")[:50])
            if ev["type"] == "result":
                print("\nRESULT OK — query_type:", ev.get("query_type"))
                print("answer:", ev["answer"].get("text", "")[:120])
                print("key_points:")
                for kp in ev["answer"].get("key_points", []):
                    print("  ▸", kp)
                break
            if ev["type"] == "error":
                print("ERROR:", ev.get("message"))
                break


if __name__ == "__main__":
    asyncio.run(main())