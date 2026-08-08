"""Tests for the sample datasets registry."""

from app.core.samples import list_samples


class TestSamples:
    def test_list_samples_returns_real_datasets(self):
        samples = list_samples()
        ids = {s["id"] for s in samples}
        assert "retail_online" in ids  # real UCI dataset
        assert "finance_bankruptcy" in ids  # real UCI dataset
        assert "marketing_shoppers" in ids  # real UCI dataset

    def test_sample_has_metadata(self):
        samples = list_samples()
        retail = next(s for s in samples if s["id"] == "retail_orders")
        assert retail["name"] == "Retail Orders"
        assert retail["domain"] == "retail"
        assert retail["description"]