"""Decompress the Kaggle Lending Club accepted loans CSV."""
import gzip
import os
import shutil

SRC = "scripts/kaggle/accepted_2007_to_2018Q4.csv.gz"
DST = "scripts/kaggle/accepted_2007_to_2018Q4.csv"


def main() -> None:
    if os.path.exists(DST):
        if os.path.isdir(DST):
            shutil.rmtree(DST)
        else:
            os.remove(DST)
    print("decompressing...")
    with gzip.open(SRC, "rb") as fin, open(DST, "wb") as fout:
        shutil.copyfileobj(fin, fout)
    print(f"done: {os.path.getsize(DST) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()