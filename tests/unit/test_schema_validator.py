"""Tests for the schema-aware SQL validator."""

from app.core.schema_validator import SchemaValidator
from app.models import ColumnInfo, SchemaMap


def _schema() -> SchemaMap:
    return SchemaMap(
        tables=["customers", "orders"],
        columns={
            "customers": [
                ColumnInfo(column="customer_id", type="TEXT", constraint="PRIMARY KEY"),
                ColumnInfo(column="region", type="TEXT"),
                ColumnInfo(column="segment", type="TEXT"),
            ],
            "orders": [
                ColumnInfo(column="order_id", type="TEXT", constraint="PRIMARY KEY"),
                ColumnInfo(column="customer_id", type="TEXT", foreign_table="customers", foreign_column="customer_id"),
                ColumnInfo(column="amount", type="DOUBLE PRECISION"),
            ],
        },
    )


class TestSchemaValidator:
    def test_valid_sql_passes(self):
        v = SchemaValidator(_schema())
        ok, fixed, errors = v.validate_and_fix(
            "SELECT region, SUM(amount) FROM orders o JOIN customers c ON c.customer_id = o.customer_id GROUP BY region"
        )
        assert ok, errors
        assert not errors

    def test_wrong_column_is_fixed(self):
        v = SchemaValidator(_schema())
        ok, fixed, errors = v.validate_and_fix(
            "SELECT state FROM customers"
        )
        # "state" is not in customers — should error (no fuzzy match to region)
        assert not ok
        assert any("state" in e for e in errors)

    def test_typo_column_is_fixed(self):
        v = SchemaValidator(_schema())
        ok, fixed, errors = v.validate_and_fix(
            "SELECT customerid FROM customers"
        )
        # "customerid" fuzzy-matches "customer_id"
        assert ok, errors
        assert "customer_id" in fixed

    def test_unknown_table_skipped(self):
        v = SchemaValidator(_schema())
        ok, fixed, errors = v.validate_and_fix(
            "WITH cte AS (SELECT 1 AS x) SELECT x FROM cte"
        )
        assert ok, errors