"""Add OpenCode Zen free models to Qwen Code's settings.json."""
import json
from pathlib import Path

p = Path.home() / ".qwen" / "settings.json"
data = json.loads(p.read_text(encoding="utf-8"))

ZEN_FREE = [
    "deepseek-v4-flash-free",
    "mimo-v2.5-free",
    "hy3-free",
    "ling-3.0-flash-free",
    "ling-3.0-tiny-free",
    "nemotron-3-ultra-free",
    "nemotron-3.5-lightning-free",
    "north-mini-code-free",
    "laguna-s-2.1-free",
    "longcat-2.0-free",
]

providers = data.setdefault("modelProviders", {}).setdefault("openai", [])
existing = {m.get("id") for m in providers}
added = 0
for mid in ZEN_FREE:
    if mid in existing:
        continue
    providers.append({
        "id": mid,
        "name": f"[OpenCode Zen] {mid}",
        "baseUrl": "https://opencode.ai/zen/v1",
        "envKey": "OPENCODE_ZEN_API_KEY",
    })
    added += 1

p.write_text(json.dumps(data, indent=2), encoding="utf-8")
print(f"added {added} Zen free models; total providers: {len(providers)}")
zen = [m["id"] for m in providers if m.get("baseUrl", "").endswith("opencode.ai/zen/v1")]
print("Zen providers:", zen)