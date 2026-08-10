"""Strip the API-injected ID column from FDIC CSVs and filter financials to active institutions."""
import csv
from pathlib import Path

DIR = Path("data/datasets/fdic")

# Active institution CERTs
with open(DIR / "institutions.csv", encoding="utf-8") as f:
    active_certs = {r["CERT"] for r in csv.DictReader(f)}
print(f"active institutions: {len(active_certs)}")

for name in ("institutions.csv", "financials.csv"):
    path = DIR / name
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cols = [c for c in reader.fieldnames if c != "ID"]
        rows = []
        for r in reader:
            if name == "financials.csv" and r["CERT"] not in active_certs:
                continue
            rows.append({c: r[c] for c in cols})
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"{name}: {len(rows)} rows, {len(cols)} cols")