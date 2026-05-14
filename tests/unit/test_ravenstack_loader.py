from pathlib import Path
from datetime import date, datetime

from scripts.load_ravenstack import (
    TABLES,
    cast_row_for_table,
    cast_csv_value,
    read_csv_rows,
)


def test_table_definitions_include_foreign_keys() -> None:
    ddl = "\n".join(table.create_sql for table in TABLES)

    assert "subscriptions" in ddl
    assert "REFERENCES accounts(account_id)" in ddl
    assert "REFERENCES subscriptions(subscription_id)" in ddl


def test_feature_usage_uses_surrogate_primary_key() -> None:
    feature_usage = next(table for table in TABLES if table.name == "feature_usage")

    assert "usage_event_id BIGSERIAL PRIMARY KEY" in feature_usage.create_sql
    assert "usage_id TEXT NOT NULL" in feature_usage.create_sql
    assert "usage_id TEXT PRIMARY KEY" not in feature_usage.create_sql


def test_cast_csv_value_handles_nulls_booleans_and_numbers() -> None:
    assert cast_csv_value("") is None
    assert cast_csv_value("True") is True
    assert cast_csv_value("False") is False
    assert cast_csv_value("42") == 42
    assert cast_csv_value("42.25") == 42.25
    assert cast_csv_value("Company_0") == "Company_0"


def test_read_csv_rows_casts_values(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text("id,flag,score,name\nA-1,True,4.5,\n", encoding="utf-8")

    rows = read_csv_rows(csv_path)

    assert rows == [{"id": "A-1", "flag": True, "score": 4.5, "name": None}]


def test_cast_row_for_table_converts_dates_and_timestamps() -> None:
    accounts_table = next(table for table in TABLES if table.name == "accounts")
    tickets_table = next(table for table in TABLES if table.name == "support_tickets")

    account_row = {"signup_date": "2024-10-16"}
    ticket_row = {
        "submitted_at": "2023-07-27",
        "closed_at": "2023-07-28 03:00:00",
    }

    assert cast_row_for_table(accounts_table, account_row)["signup_date"] == date(
        2024, 10, 16
    )
    assert cast_row_for_table(tickets_table, ticket_row)["submitted_at"] == datetime(
        2023, 7, 27
    )
    assert cast_row_for_table(tickets_table, ticket_row)["closed_at"] == datetime(
        2023, 7, 28, 3
    )
