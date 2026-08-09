"""Tests for the multi-table dataset loader."""

from app.core.dataset_loader import list_datasets


class TestDatasets:
    def test_list_datasets_returns_retail(self):
        datasets = list_datasets()
        assert any(d["id"] == "retail" for d in datasets)

    def test_retail_dataset_metadata(self):
        datasets = list_datasets()
        retail = next(d for d in datasets if d["id"] == "retail")
        assert retail["name"] == "Retail Commerce"
        assert retail["domain"] == "retail"
        assert retail["description"]