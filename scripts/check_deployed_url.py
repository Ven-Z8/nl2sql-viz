"""Find the baked API URL in the deployed frontend chunks."""
import re
import urllib.request

BASE = "https://ven-z8.github.io/nl2sql-viz"
html = urllib.request.urlopen(f"{BASE}/", timeout=30).read().decode("utf-8", "replace")
chunks = sorted(set(re.findall(r"/_next/static/chunks/[^\"']+\.js", html)))
print(f"{len(chunks)} unique chunks")

patterns = ["localhost:8000", "duckdns", "onrender", "nl2sql2viz", "ws://", "wss://"]
for c in chunks:
    try:
        js = urllib.request.urlopen(BASE + c, timeout=30).read().decode("utf-8", "replace")
    except Exception:
        continue
    hits = [p for p in patterns if p in js]
    if hits:
        urls = set(re.findall(r"https?://[a-zA-Z0-9.\-]+[^\"'\s]*", js))
        ws = set(re.findall(r"wss?://[a-zA-Z0-9.\-]+[^\"'\s]*", js))
        print(f"\n{c}")
        print("  patterns:", hits)
        print("  http urls:", [u for u in urls if "duckdns" in u or "onrender" in u or "localhost" in u][:4])
        print("  ws urls:", [u for u in ws if "duckdns" in u or "onrender" in u or "localhost" in u][:4])