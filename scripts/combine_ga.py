"""Combine monthly Divvy trip CSVs into one trips.csv."""
import csv
import shutil
from pathlib import Path

SRC = Path("data/datasets/ga")
OUT = SRC / "trips.csv"

header = None
total = 0
with open(OUT, "w", newline="", encoding="utf-8") as out:
    writer = None
    for month_dir in sorted(SRC.glob("2021*-divvy-tripdata")):
        csv_file = next(month_dir.glob("*.csv"))
        with open(csv_file, encoding="utf-8") as f:
            reader = csv.reader(f)
            h = next(reader)
            if header is None:
                header = h
                writer = csv.writer(out)
                writer.writerow(header)
            assert h == header, f"header mismatch in {csv_file}"
            for row in reader:
                writer.writerow(row)
                total += 1
        print(f"  {month_dir.name}: done")
print(f"total rows: {total:,}")

# Remove monthly folders to save space
for month_dir in SRC.glob("2021*-divvy-tripdata"):
    shutil.rmtree(month_dir)
print("removed monthly folders")