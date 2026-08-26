"""Tests for dataset_loader focus-table selection (schema-scoping root)."""

import pytest

from app.core.dataset_loader import _pick_focus


def _t(name: str, fks: list[str]) -> dict:
    return {"name": name, "columns": [{"name": "x", "type": "int"}] + [
        {"name": f"fk{i}", "type": "int", "fk": fk} for i, fk in enumerate(fks)
    ]}


def test_star_schema_picks_fact_table():
    tables = [
        _t("dim_a", []),
        _t("dim_b", []),
        _t("fact", ["dim_a.pk", "dim_b.pk"]),
    ]
    assert _pick_focus(tables) == "fact"


def test_hub_between_two_dims():
    # worldbank shape: values joins countries + indicators
    tables = [
        _t("countries", []),
        _t("indicators", []),
        _t("values", ["countries.country_code", "indicators.indicator_code"]),
    ]
    assert _pick_focus(tables) == "values"


def test_single_table():
    assert _pick_focus([_t("only", [])]) == "only"


def test_chain_reaches_whole_graph():
    tables = [
        _t("a", []),
        _t("b", ["a.pk"]),
        _t("c", ["b.pk"]),
    ]
    # b has degree 2 (one out-FK, one referenced) — mid-chain hub is fine;
    # any node of the single component scopes the same graph.
    assert _pick_focus(tables) == "b"


def test_empty_raises():
    with pytest.raises(KeyError):
        _pick_focus([])
