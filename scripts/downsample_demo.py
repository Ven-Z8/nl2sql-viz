"""Build demo-sized data files by streaming (no full extraction).

- finance_lending.csv: stream from accepted_2007_to_2018Q4.csv.gz, keep every
  Nth row (~130K rows) — the gz is small, the raw CSV would be 1.7GB.
- ga/trips.csv: stream-combine the 12 monthly trip CSVs, keep every Nth row
  (~250K rows) — the full combined file is ~1GB.
Both stay under GitHub's 100MB file limit.
"""
import csv
import gzip
from pathlib import Path


def gz_downsample(gz_path: str, dst: str, target: int) -> None:
    with gzip.open(gz_path, "rt", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        total = 0
        for _ in reader:
            total += 1
    print(f"{Path(gz_path).name}: {total:,} rows")
    step = total / target
    picked = 0
    with gzip.open(gz_path, "rt", encoding="utf-8", errors="replace", newline="") as f, open(dst, "w", encoding="utf-8", newline="") as out:
        reader = csv.reader(f)
        writer = csv.writer(out)
        writer.writerow(next(reader))
        for i, row in enumerate(reader):
            if int(i / step) == picked:
                writer.writerow(row)
                picked += 1
    print(f"wrote {picked:,} rows -> {dst}")


def ga_combine_downsample(src_dir: str, dst: str, target: int) -> None:
    monthly = sorted(Path(src_dir).glob("2021*-divvy-tripdata/*.csv"))
    header = None
    total = 0
    for p in monthly:
        with open(p, encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            if header is None:
                header = next(reader)
            else:
                next(reader)
            for _ in reader:
                total += 1
    print(f"ga total: {total:,} rows across {len(monthly)} files")
    step = total / target
    picked = 0
    global_i = 0
    with open(dst, "w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(header)
        for p in monthly:
            with open(p, encoding="utf-8", newline="") as f:
                reader = csv.reader(f)
                next(reader)  # header
                for row in reader:
                    if int(global_i / step) == picked:
                        writer.writerow(row)
                        picked += 1
                    global_i += 1
    print(f"wrote {picked:,} rows -> {dst}")


if __name__ == "__main__":
    gz_downsample(
        "C:/Users/venki/portfolio/nl2sql-viz/data/samples/raw_lending/accepted_2007_to_2018Q4.csv.gz",
        "C:/Users/venki/portfolio/nl2sql-viz/data/samples/finance_lending.csv",
        130_000,
    )
    ga_combine_downsample(
        "C:/Users/venki/portfolio/nl2sql-viz/data/datasets/ga",
        "C:/Users/venki/portfolio/nl2sql-viz/data/datasets/ga/trips.csv",
        250_000,
    )