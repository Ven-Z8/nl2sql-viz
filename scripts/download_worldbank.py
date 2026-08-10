"""Download World Bank WDI data via API into a 3-table relational extract.

countries (code, name, region, income_level) · indicators (code, name, topic)
· values (country_code, indicator_code, year, value) — long format.
Aggregate/region codes are filtered at download time so values only reference
real countries.
"""
import csv
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path("data/datasets/worldbank")
OUT.mkdir(parents=True, exist_ok=True)

BASE = "https://api.worldbank.org/v2"

INDICATORS = {
    "NY.GDP.MKTP.CD": "GDP (current US$)",
    "NY.GDP.PCAP.CD": "GDP per capita (current US$)",
    "NY.GDP.MKTP.KD.ZG": "GDP growth (annual %)",
    "SP.POP.TOTL": "Population, total",
    "SP.POP.TOTL.FE.ZS": "Population, female (% of total)",
    "SP.URB.TOTL.IN.ZS": "Urban population (% of total)",
    "SP.DYN.LE00.IN": "Life expectancy at birth (years)",
    "SP.DYN.TFRT.IN": "Fertility rate (births per woman)",
    "SP.DYN.CBRT.IN": "Birth rate (per 1,000 people)",
    "SP.DYN.CDRT.IN": "Death rate (per 1,000 people)",
    "SP.POP.65UP.TO.ZS": "Population ages 65+ (% of total)",
    "SP.POP.0014.TO.ZS": "Population ages 0-14 (% of total)",
    "SL.UEM.TOTL.ZS": "Unemployment (% of labor force)",
    "SL.TLF.CACT.FE.ZS": "Female labor force participation (%)",
    "SI.POV.DDAY": "Poverty headcount at $2.15/day (%)",
    "SI.POV.GINI": "Gini index",
    "SE.XPD.TOTL.GD.ZS": "Education expenditure (% of GDP)",
    "SH.XPD.CHEX.GD.ZS": "Health expenditure (% of GDP)",
    "SH.DYN.MORT": "Infant mortality (per 1,000 live births)",
    "AG.LND.AGRI.ZS": "Agricultural land (% of land area)",
    "EG.USE.COMM.FO.ZS": "Fossil fuel energy consumption (% of total)",
    "EG.USE.ELEC.KH.PC": "Electricity use (kWh per capita)",
    "IT.NET.USER.ZS": "Internet users (% of population)",
    "TX.VAL.TECH.MF.ZS": "High-technology exports (% of manufactured)",
    "NE.TRD.GNFS.ZS": "Trade (% of GDP)",
    "BN.CAB.XOKA.GD.ZS": "Current account balance (% of GDP)",
    "FR.INR.LEND": "Lending interest rate (%)",
    "FP.CPI.TOTL.ZG": "Inflation, consumer prices (annual %)",
    "MS.MIL.XPND.GD.ZS": "Military expenditure (% of GDP)",
    "SG.GEN.PARL.ZS": "Women in parliament (%)",
    "SE.ADT.LITR.ZS": "Literacy rate, adult (%)",
    "SH.STA.ANVC.ZS": "Antenatal care coverage (%)",
    "SN.ITK.DEFC.ZS": "Prevalence of undernourishment (%)",
    "SP.RUR.TOTL.ZS": "Rural population (% of total)",
    "NY.GDP.PETR.RT.ZS": "Oil rents (% of GDP)",
    "EG.USE.PCAP.KG.OE": "Energy use (kg of oil equivalent per capita)",
    "IS.AIR.PSGR": "Air transport, passengers carried",
    "ST.INT.ARVL": "International tourism, arrivals",
    "EN.URB.LCTY.UR.ZS": "Population in largest city (%)",
    "SP.DYN.IMRT.IN": "Mortality rate, infant (per 1,000 live births)",
}


def get_json(url: str) -> list:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (nl2sql-viz data loader)"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode())
        except (urllib.error.HTTPError, TimeoutError, urllib.error.URLError, OSError, MemoryError) as e:
            if attempt < 5:
                time.sleep(4 * (attempt + 1))
                continue
            raise RuntimeError(f"{type(e).__name__} for {url}: {e}")
    raise RuntimeError(f"failed after retries: {url}")


def main() -> None:
    # 1. Countries
    countries = []
    page = 1
    while True:
        data = get_json(f"{BASE}/country?format=json&per_page=500&page={page}")
        if not isinstance(data, list) or len(data) < 2 or not data[1]:
            break
        for c in data[1]:
            if c["region"]["value"] == "Aggregates":
                continue
            countries.append({
                # iso2Code matches the indicator endpoint's country.id (2-letter)
                "country_code": c["iso2Code"],
                "country_name": c["name"],
                "region": c["region"]["value"],
                "income_level": c["incomeLevel"]["value"],
            })
        if page >= data[0]["pages"]:
            break
        page += 1
        time.sleep(0.3)
    valid_codes = {c["country_code"] for c in countries}
    print(f"countries: {len(countries)}")

    with open(OUT / "countries.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["country_code", "country_name", "region", "income_level"])
        w.writeheader()
        w.writerows(countries)
    with open(OUT / "indicators.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["indicator_code", "indicator_name", "topic"])
        w.writeheader()
        w.writerows([{"indicator_code": k, "indicator_name": v, "topic": "WDI"} for k, v in INDICATORS.items()])
    print("wrote countries.csv, indicators.csv")

    # 2. Values — skip aggregate codes at download time
    total = 0
    with open(OUT / "values.csv", "w", newline="", encoding="utf-8") as vf:
        w = csv.DictWriter(vf, fieldnames=["country_code", "indicator_code", "year", "value"])
        w.writeheader()
        for i, code in enumerate(INDICATORS, 1):
            print(f"  indicator {i}/{len(INDICATORS)}: {code}")
            page = 1
            while True:
                params = urllib.parse.urlencode({
                    "format": "json", "per_page": "5000", "page": str(page), "date": "1960:2023",
                })
                data = get_json(f"{BASE}/country/all/indicator/{code}?{params}")
                if not isinstance(data, list) or len(data) < 2 or not data[1]:
                    break
                for rec in data[1]:
                    if rec["value"] is None:
                        continue
                    cc = rec["country"]["id"]
                    if cc not in valid_codes:
                        continue  # aggregate / region code
                    w.writerow({
                        "country_code": cc,
                        "indicator_code": code,
                        "year": int(rec["date"]),
                        "value": float(rec["value"]),
                    })
                    total += 1
                if page >= data[0]["pages"]:
                    break
                page += 1
                time.sleep(1.0)
            time.sleep(0.5)
    print(f"wrote values.csv: {total:,} rows")


if __name__ == "__main__":
    main()