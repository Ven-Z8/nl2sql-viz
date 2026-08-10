"""Download FDIC bank data (institutions + financials) via the public API."""
import csv
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path("data/datasets/fdic")
OUT.mkdir(parents=True, exist_ok=True)

BASE = "https://api.fdic.gov/banks"

INST_FIELDS = "NAME,CERT,CITY,STNAME,STALP,ASSET,DEP,NETINC,ROA,ROE,BKCLASS,OFFICES,ESTYMD,LATITUDE,LONGITUDE,ACTIVE"
FIN_FIELDS = "CERT,REPDTE,ASSET,DEP,LIAB,NETINC,ROA,ROE,INTINC,EXP,TAX"


def fetch(endpoint: str, fields: str, filters: str, limit: int = 10000) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        params = {
            "fields": fields,
            "filters": filters,
            "limit": str(limit),
            "offset": str(offset),
            "format": "json",
        }
        url = f"{BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
        with urllib.request.urlopen(url, timeout=120) as r:
            data = json.loads(r.read().decode())
        batch = [d["data"] for d in data.get("data", [])]
        rows.extend(batch)
        total = data.get("totals", {}).get("count", 0)
        offset += len(batch)
        print(f"  {endpoint}: {len(rows)}/{total}")
        if not batch or offset >= total:
            break
        time.sleep(0.3)
    return rows


def write_csv(name: str, rows: list[dict]) -> None:
    if not rows:
        return
    cols = list(rows[0].keys())
    with open(OUT / name, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"  wrote {name}: {len(rows)} rows, {len(cols)} cols")


def main() -> None:
    print("institutions...")
    inst = fetch("institutions", INST_FIELDS, "ACTIVE:1")
    write_csv("institutions.csv", inst)

    print("financials (2020-2024, quarterly)...")
    fin: list[dict] = []
    for year in range(2020, 2025):
        for month in ("0331", "0630", "0930", "1231"):
            fin.extend(fetch("financials", FIN_FIELDS, f"REPDTE:{year}{month}"))
    write_csv("financials.csv", fin)


if __name__ == "__main__":
    main()