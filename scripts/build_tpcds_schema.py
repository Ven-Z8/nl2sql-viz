"""Build TPC-DS schema.json from the DuckDB dump + known FK/PK map."""
import json
import re
from pathlib import Path

DUMP = json.loads(Path("scripts/tpcds_schema_dump.json").read_text(encoding="utf-8"))

# TPC-DS primary keys
PKS = {
    "call_center": "cc_call_center_sk", "catalog_page": "cp_catalog_page_sk",
    "customer": "c_customer_sk", "customer_address": "ca_address_sk",
    "customer_demographics": "cd_demo_sk", "date_dim": "d_date_sk",
    "household_demographics": "hd_demo_sk", "income_band": "ib_income_band_sk",
    "item": "i_item_sk", "promotion": "p_promo_sk", "reason": "r_reason_sk",
    "ship_mode": "sm_ship_mode_sk", "store": "s_store_sk", "time_dim": "t_time_sk",
    "warehouse": "w_warehouse_sk", "web_page": "wp_web_page_sk", "web_site": "web_site_sk",
}

# TPC-DS foreign keys: table -> {column: "ref_table.ref_column"}
FKS = {
    "customer": {
        "c_current_addr_sk": "customer_address.ca_address_sk",
        "c_current_cdemo_sk": "customer_demographics.cd_demo_sk",
        "c_current_hdemo_sk": "household_demographics.hd_demo_sk",
        "c_first_sales_date_sk": "date_dim.d_date_sk",
        "c_first_shipto_date_sk": "date_dim.d_date_sk",
    },
    "store_sales": {
        "ss_sold_date_sk": "date_dim.d_date_sk", "ss_sold_time_sk": "time_dim.t_time_sk",
        "ss_item_sk": "item.i_item_sk", "ss_customer_sk": "customer.c_customer_sk",
        "ss_cdemo_sk": "customer_demographics.cd_demo_sk",
        "ss_hdemo_sk": "household_demographics.hd_demo_sk",
        "ss_addr_sk": "customer_address.ca_address_sk", "ss_store_sk": "store.s_store_sk",
        "ss_promo_sk": "promotion.p_promo_sk",
    },
    "store_returns": {
        "sr_returned_date_sk": "date_dim.d_date_sk", "sr_return_time_sk": "time_dim.t_time_sk",
        "sr_item_sk": "item.i_item_sk", "sr_customer_sk": "customer.c_customer_sk",
        "sr_cdemo_sk": "customer_demographics.cd_demo_sk",
        "sr_hdemo_sk": "household_demographics.hd_demo_sk",
        "sr_addr_sk": "customer_address.ca_address_sk", "sr_store_sk": "store.s_store_sk",
        "sr_reason_sk": "reason.r_reason_sk",
    },
    "catalog_sales": {
        "cs_sold_date_sk": "date_dim.d_date_sk", "cs_sold_time_sk": "time_dim.t_time_sk",
        "cs_ship_date_sk": "date_dim.d_date_sk",
        "cs_bill_customer_sk": "customer.c_customer_sk",
        "cs_bill_cdemo_sk": "customer_demographics.cd_demo_sk",
        "cs_bill_hdemo_sk": "household_demographics.hd_demo_sk",
        "cs_bill_addr_sk": "customer_address.ca_address_sk",
        "cs_ship_customer_sk": "customer.c_customer_sk",
        "cs_ship_cdemo_sk": "customer_demographics.cd_demo_sk",
        "cs_ship_hdemo_sk": "household_demographics.hd_demo_sk",
        "cs_ship_addr_sk": "customer_address.ca_address_sk",
        "cs_call_center_sk": "call_center.cc_call_center_sk",
        "cs_catalog_page_sk": "catalog_page.cp_catalog_page_sk",
        "cs_ship_mode_sk": "ship_mode.sm_ship_mode_sk",
        "cs_warehouse_sk": "warehouse.w_warehouse_sk",
        "cs_item_sk": "item.i_item_sk", "cs_promo_sk": "promotion.p_promo_sk",
    },
    "catalog_returns": {
        "cr_returned_date_sk": "date_dim.d_date_sk", "cr_returned_time_sk": "time_dim.t_time_sk",
        "cr_item_sk": "item.i_item_sk",
        "cr_refunded_customer_sk": "customer.c_customer_sk",
        "cr_refunded_cdemo_sk": "customer_demographics.cd_demo_sk",
        "cr_refunded_hdemo_sk": "household_demographics.hd_demo_sk",
        "cr_refunded_addr_sk": "customer_address.ca_address_sk",
        "cr_returning_customer_sk": "customer.c_customer_sk",
        "cr_returning_cdemo_sk": "customer_demographics.cd_demo_sk",
        "cr_returning_hdemo_sk": "household_demographics.hd_demo_sk",
        "cr_returning_addr_sk": "customer_address.ca_address_sk",
        "cr_call_center_sk": "call_center.cc_call_center_sk",
        "cr_catalog_page_sk": "catalog_page.cp_catalog_page_sk",
        "cr_ship_mode_sk": "ship_mode.sm_ship_mode_sk",
        "cr_warehouse_sk": "warehouse.w_warehouse_sk",
        "cr_reason_sk": "reason.r_reason_sk",
    },
    "web_sales": {
        "ws_sold_date_sk": "date_dim.d_date_sk", "ws_sold_time_sk": "time_dim.t_time_sk",
        "ws_ship_date_sk": "date_dim.d_date_sk",
        "ws_item_sk": "item.i_item_sk",
        "ws_bill_customer_sk": "customer.c_customer_sk",
        "ws_bill_cdemo_sk": "customer_demographics.cd_demo_sk",
        "ws_bill_hdemo_sk": "household_demographics.hd_demo_sk",
        "ws_bill_addr_sk": "customer_address.ca_address_sk",
        "ws_ship_customer_sk": "customer.c_customer_sk",
        "ws_ship_cdemo_sk": "customer_demographics.cd_demo_sk",
        "ws_ship_hdemo_sk": "household_demographics.hd_demo_sk",
        "ws_ship_addr_sk": "customer_address.ca_address_sk",
        "ws_web_page_sk": "web_page.wp_web_page_sk",
        "ws_web_site_sk": "web_site.web_site_sk",
        "ws_ship_mode_sk": "ship_mode.sm_ship_mode_sk",
        "ws_warehouse_sk": "warehouse.w_warehouse_sk",
        "ws_promo_sk": "promotion.p_promo_sk",
    },
    "web_returns": {
        "wr_returned_date_sk": "date_dim.d_date_sk", "wr_returned_time_sk": "time_dim.t_time_sk",
        "wr_item_sk": "item.i_item_sk",
        "wr_refunded_customer_sk": "customer.c_customer_sk",
        "wr_refunded_cdemo_sk": "customer_demographics.cd_demo_sk",
        "wr_refunded_hdemo_sk": "household_demographics.hd_demo_sk",
        "wr_refunded_addr_sk": "customer_address.ca_address_sk",
        "wr_returning_customer_sk": "customer.c_customer_sk",
        "wr_returning_cdemo_sk": "customer_demographics.cd_demo_sk",
        "wr_returning_hdemo_sk": "household_demographics.hd_demo_sk",
        "wr_returning_addr_sk": "customer_address.ca_address_sk",
        "wr_web_page_sk": "web_page.wp_web_page_sk",
        "wr_reason_sk": "reason.r_reason_sk",
    },
    "inventory": {
        "inv_date_sk": "date_dim.d_date_sk",
        "inv_item_sk": "item.i_item_sk",
        "inv_warehouse_sk": "warehouse.w_warehouse_sk",
    },
}

TYPE_MAP = {
    "BIGINT": "BIGINT", "INTEGER": "BIGINT", "HUGEINT": "BIGINT",
    "VARCHAR": "TEXT", "CHAR": "TEXT", "DATE": "DATE", "TIME": "TEXT",
}


def pg_type(t: str) -> str:
    if t.startswith("DECIMAL"):
        return "DOUBLE PRECISION"
    return TYPE_MAP.get(t, "TEXT")


def deps(table: str) -> list[str]:
    return [fk.split(".")[0] for fk in FKS.get(table, {}).values()]


# Topological order: parents before children
tables = list(DUMP.keys())
ordered: list[str] = []
remaining = set(tables)
while remaining:
    ready = [t for t in remaining if all(d in ordered for d in deps(t))]
    if not ready:
        raise RuntimeError(f"cycle among: {remaining}")
    ordered.extend(sorted(ready))
    remaining -= set(ready)

schema_tables = []
for t in ordered:
    cols = []
    for c in DUMP[t]:
        entry = {"name": c["name"], "type": pg_type(c["type"])}
        if PKS.get(t) == c["name"]:
            entry["pk"] = True
        if t in FKS and c["name"] in FKS[t]:
            entry["fk"] = FKS[t][c["name"]]
        cols.append(entry)
    schema_tables.append({"name": t, "columns": cols})

schema = {
    "name": "TPC-DS Benchmark",
    "domain": "operations",
    "description": "TPC-DS decision-support benchmark (SF=0.01) — 24 tables, store/catalog/web sales + returns, inventory, customers (~277K rows)",
    "tables": schema_tables,
}
Path("data/datasets/tpcds/schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
print(f"wrote schema.json: {len(schema_tables)} tables, {sum(len(t['columns']) for t in schema_tables)} columns")
print("order:", ordered)