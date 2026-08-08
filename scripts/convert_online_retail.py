"""Convert the UCI Online Retail II xlsx to CSV for upload testing."""
import csv
import sys

import openpyxl

SRC = "scripts/online_retail_ii/online_retail_II.xlsx"
DST = "scripts/online_retail_ii.csv"


def main() -> int:
    wb = openpyxl.load_workbook(SRC, read_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    header = next(rows)
    count = 0
    with open(DST, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for row in rows:
            writer.writerow(["" if v is None else v for v in row])
            count += 1
    print(f"wrote {count} rows to {DST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())