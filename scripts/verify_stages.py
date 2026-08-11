"""Verify the live backend emits stage-tagged progress events."""
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

    async with websockets.connect(WS, open_timeout=30, ping_interval=None, ping_timeout=None) as ws:
        await ws.send(json.dumps({"type": "auth", "api_key": api_key}))
        await asyncio.wait_for(ws.recv(), timeout=30)
        await ws.send(json.dumps({"type": "query", "query": QUESTION, "dsn": dsn}))
        stages = []
        while True:
            ev = json.loads(await asyncio.wait_for(ws.recv(), timeout=600))
            if ev["type"] == "progress":
                stages.append(ev.get("stage", "NO-STAGE"))
                print(f"  [{ev.get('stage','?')}] {ev.get('message','')[:50]}")
            if ev["type"] == "result":
                print("\nRESULT OK — stages seen:", stages)
                break
            if ev["type"] == "error":
                print("ERROR:", ev.get("message"))
                break


if __name__ == "__main__":
    asyncio.run(main())