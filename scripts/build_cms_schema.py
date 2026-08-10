"""Build CMS schema.json from the claims.csv header."""
import csv
import json
from pathlib import Path

with open("data/datasets/cms/claims.csv", encoding="utf-8") as f:
    header = next(csv.reader(f))

TEXT_COLS = {
    "DESYNPUF_ID", "CLM_ID", "PRVDR_NUM", "AT_PHYSN_NPI", "OP_PHYSN_NPI",
    "OT_PHYSN_NPI", "ADMTNG_ICD9_DGNS_CD", "CLM_DRG_CD", "CLM_FROM_DT",
    "CLM_THRU_DT", "CLM_ADMSN_DT", "NCH_BENE_DSCHRG_DT",
}
MONEY_COLS = {
    "CLM_PMT_AMT", "NCH_PRMRY_PYR_CLM_PD_AMT", "CLM_PASS_THRU_PER_DIEM_AMT",
    "NCH_BENE_IP_DDCTBL_AMT", "NCH_BENE_PTA_COINSRNC_LBLTY_AM",
    "NCH_BENE_BLOOD_DDCTBL_LBLTY_AM",
}

cols = []
for c in header:
    if c in TEXT_COLS:
        t = "TEXT"
    elif c in MONEY_COLS:
        t = "DOUBLE PRECISION"
    elif c == "CLM_UTLZTN_DAY_CNT":
        t = "BIGINT"
    elif c == "SEGMENT":
        t = "BIGINT"
    else:
        t = "TEXT"  # ICD9/HCPCS codes
    cols.append({"name": c, "type": t})

schema = {
    "name": "CMS Medicare Inpatient Claims",
    "domain": "healthcare",
    "description": "Real CMS SynPUF synthetic Medicare inpatient claims — 1.33M claims (2008-2010), 81 columns: payments, DRG, ICD-9 diagnoses/procedures (public domain)",
    "tables": [{"name": "claims", "columns": cols}],
}
Path("data/datasets/cms/schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
print(f"wrote schema.json: {len(cols)} columns")