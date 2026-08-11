"""Analyze benchmark results: query types + latency distribution."""
import collections
import glob
import json
import statistics

allr = [r for p in glob.glob("data/benchmark/*.json") for r in json.load(open(p, encoding="utf-8"))]

qt = collections.Counter(r.get("query_type") for r in allr if r["success"])
print("query types:", dict(qt))

tiers = collections.defaultdict(list)
for r in allr:
    if r.get("wall_time_s"):
        tiers[r["tier"]].append(r["wall_time_s"])

for t in ["easy", "medium", "hard", "very_complex"]:
    s = sorted(tiers.get(t, []))
    if s:
        n = len(s)
        p90 = s[int(n * 0.9) - 1]
        print(f"{t}: n={n} median={statistics.median(s):.0f}s p90={p90:.0f}s max={max(s):.0f}s")

# Slowest questions
print("\nslowest 8:")
for r in sorted(allr, key=lambda r: r.get("wall_time_s", 0), reverse=True)[:8]:
    print(f"  {r['wall_time_s']:.0f}s {r['dataset']} [{r['tier']}] {r['question'][:60]}")