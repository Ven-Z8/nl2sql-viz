"""Tests for CSV ingestion — parsing, type inference, table naming."""

import pytest

from app.core.csv_loader import (
    CSVUploadError,
    infer_schema,
    parse_csv,
    sanitize_table_name,
)


class TestSanitizeTableName:
    def test_basic(self):
        assert sanitize_table_name("sales_data.csv") == "upload_sales_data"

    def test_spaces_and_special_chars(self):
        assert sanitize_table_name("My Sales Data (2024).csv") == "upload_my_sales_data_2024"

    def test_uppercase(self):
        assert sanitize_table_name("ORDERS.CSV") == "upload_orders"

    def test_empty(self):
        with pytest.raises(CSVUploadError):
            sanitize_table_name("!!!.csv")


class TestParseCsv:
    def test_parses_header_and_rows(self):
        content = b"name,age\nAlice,30\nBob,25\n"
        columns, rows = parse_csv(content)
        assert columns == ["name", "age"]
        assert rows == [{"name": "Alice", "age": "30"}, {"name": "Bob", "age": "25"}]

    def test_utf8_bom(self):
        content = b"\xef\xbb\xbfname,age\nAlice,30\n"
        columns, _ = parse_csv(content)
        assert columns == ["name", "age"]

    def test_no_header(self):
        with pytest.raises(CSVUploadError, match="header"):
            parse_csv(b"\n\n")

    def test_no_rows(self):
        with pytest.raises(CSVUploadError, match="data rows"):
            parse_csv(b"name,age\n")

    def test_bad_encoding(self):
        with pytest.raises(CSVUploadError, match="UTF-8"):
            parse_csv(b"\xff\xfe\x00name,age\n")


class TestInferSchema:
    def test_int_float_date_text(self):
        rows = [
            {"id": "1", "price": "9.99", "date": "2024-01-15", "name": "Widget"},
            {"id": "2", "price": "19.50", "date": "2024-02-01", "name": "Gadget"},
        ]
        types = infer_schema(["id", "price", "date", "name"], rows)
        assert types["id"] == "BIGINT"
        assert types["price"] == "DOUBLE PRECISION"
        assert types["date"] == "DATE"
        assert types["name"] == "TEXT"

    def test_mixed_column_falls_back_to_text(self):
        rows = [{"v": "1"}, {"v": "abc"}]
        types = infer_schema(["v"], rows)
        assert types["v"] == "TEXT"

    def test_empty_values_ignored(self):
        rows = [{"v": ""}, {"v": "5"}]
        types = infer_schema(["v"], rows)
        assert types["v"] == "BIGINT"