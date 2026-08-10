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

    def test_case_mismatch_is_fixed(self):
        # Postgres quoted identifiers are case-sensitive: "State" != state.
        # A case-insensitive match must be REWRITTEN to the real name, not
        # passed through (which would fail at execution).
        schema = SchemaMap(
            tables=["tracts"],
            columns={"tracts": [ColumnInfo(column="State", type="TEXT")]},
        )
        v = SchemaValidator(schema)
        ok, fixed, errors = v.validate_and_fix("SELECT state FROM tracts")
        assert ok, errors
        assert '"State"' in fixed, fixed

    def test_exact_case_match_passes_unchanged(self):
        schema = SchemaMap(
            tables=["tracts"],
            columns={"tracts": [ColumnInfo(column="State", type="TEXT")]},
        )
        v = SchemaValidator(schema)
        ok, fixed, errors = v.validate_and_fix('SELECT "State" FROM tracts')
        assert ok, errors
        assert fixed == 'SELECT "State" FROM tracts'

    def test_unquoted_uppercase_is_quoted(self):
        # The model may emit `State` unquoted — Postgres folds it to lowercase
        # and fails. The validator must quote it even on an exact match.
        schema = SchemaMap(
            tables=["tracts"],
            columns={"tracts": [ColumnInfo(column="State", type="TEXT")]},
        )
        v = SchemaValidator(schema)
        ok, fixed, errors = v.validate_and_fix("SELECT State FROM tracts")
        assert ok, errors
        assert '"State"' in fixed, fixed

    def test_bare_column_must_exist_in_query_tables(self):
        # A column that exists in an UNRELATED table must not pass validation
        # unchanged — it must be rewritten to a real column of the query's
        # FROM table (or rejected).
        schema = SchemaMap(
            tables=["sales", "customers"],
            columns={
                "sales": [ColumnInfo(column="region", type="TEXT"), ColumnInfo(column="amount", type="TEXT")],
                "customers": [ColumnInfo(column="region_id", type="TEXT")],
            },
        )
        v = SchemaValidator(schema)
        ok, fixed, errors = v.validate_and_fix("SELECT region_id FROM sales")
        assert ok, errors
        assert '"region"' in fixed, fixed
        assert '"region_id"' not in fixed

    def test_bare_column_fuzzy_fixed_within_query_tables(self):
        schema = SchemaMap(
            tables=["sales"],
            columns={"sales": [ColumnInfo(column="region", type="TEXT"), ColumnInfo(column="amount", type="TEXT")]},
        )
        v = SchemaValidator(schema)
        ok, fixed, errors = v.validate_and_fix("SELECT regionid FROM sales")
        assert ok, errors
        assert '"region"' in fixed, fixed