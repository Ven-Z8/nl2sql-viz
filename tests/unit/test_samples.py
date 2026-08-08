"""Tests for the sample datasets registry."""

from app.core.samples import list_samples


class TestSamples:
    def test_list_samples_returns_retail_orders(self):
        samples = list_samples()
        assert any(s["id"] == "retail_orders" for s in samples)

    def test_sample_has_metadata(self):
        samples = list_samples()
        retail = next(s for s in samples if s["id"] == "retail_orders")
        assert retail["name"] == "Retail Orders"
        assert retail["domain"] == "retail"
        assert retail["description"]