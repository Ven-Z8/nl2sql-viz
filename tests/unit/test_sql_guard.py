import pytest

from app.core.sql_guard import validate_read_only_sql


def test_validate_read_only_sql_rejects_mutating_cte() -> None:
    sql = "WITH deleted AS (DELETE FROM sales RETURNING *) SELECT * FROM deleted"

    with pytest.raises(ValueError, match="mutating keyword"):
        validate_read_only_sql(sql)


def test_validate_read_only_sql_accepts_select_and_read_only_cte() -> None:
    validate_read_only_sql("SELECT region, SUM(amount) FROM sales GROUP BY region")
    validate_read_only_sql(
        "WITH totals AS (SELECT region, SUM(amount) AS total FROM sales GROUP BY region) "
        "SELECT * FROM totals"
    )


def test_validate_read_only_sql_rejects_multiple_statements() -> None:
    with pytest.raises(ValueError, match="single statement"):
        validate_read_only_sql("SELECT 1; SELECT 2")
