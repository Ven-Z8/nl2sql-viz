"""Validate all 12 questions.json files."""
import glob
import json

for p in sorted(glob.glob("data/datasets/*/questions.json")):
    d = json.load(open(p, encoding="utf-8"))
    assert set(d) == {"easy", "medium", "hard", "very_complex"}, p
    n = sum(len(v) for v in d.values())
    counts = {k: len(v) for k, v in d.items()}
    print(f"{p.split(chr(92))[-2]:24s} {n} questions {counts}")