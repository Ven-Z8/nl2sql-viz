"""Generate TPC-DS data at SF=0.01 via DuckDB and export to CSVs."""
import duckdb
from pathlib import Path

OUT = Path("data/datasets/tpcds")
OUT.mkdir(parents=True, exist_ok=True)

con = duckdb.connect()
con.execute("INSTALL tpcds; LOAD tpcds;")
con.execute("CALL dsdgen(sf=0.01);")

tables = con.execute("SHOW TABLES").fetchall()
print(f"{len(tables)} tables generated")
for (t,) in tables:
    n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    con.execute(f"COPY (SELECT * FROM {t}) TO '{OUT / (t + '.csv')}' (HEADER, DELIMITER ',')")
    print(f"  {t}: {n:,} rows")
con.close()