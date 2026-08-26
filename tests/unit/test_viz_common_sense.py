"""Common-sense rules in VizAgent: primary measure, top_n, long-format pivot."""
from app.agents.viz_agent import VizAgent
from app.models import QueryResult


def _result(rows: list[dict], row_count: int | None = None) -> QueryResult:
    return QueryResult(
        sql="SELECT 1",
        columns=list(rows[0].keys()) if rows else [],
        rows=rows,
        row_count=row_count if row_count is not None else len(rows),
    )


def test_primary_measure_matches_question_tokens():
    rows = [
        {"state": f"s{i}", "median_income": i, "avg_county_income": i * 2,
         "min_county_income": 0, "max_county_income": i * 3}
        for i in range(20)
    ]
    hint = VizAgent().build_chart_hint(
        "How does median income vary across states?", _result(rows)
    )
    # 4 measures x 52 states would be a wall — plot the asked-about one.
    assert hint["kind"] == "bar"
    assert hint["y"] == ["median_income"]
    assert hint["top_n"] == 12
    assert hint["sort"] == "desc"


def test_grouped_bar_kept_when_small():
    rows = [
        {"category": c, "sales": i, "profit": i / 2}
        for i, c in enumerate(["a", "b", "c", "d", "e"])
    ]
    hint = VizAgent().build_chart_hint("Compare sales and profit by category", _result(rows))
    assert hint["kind"] == "grouped_bar"
    assert set(hint["y"]) == {"sales", "profit"}


def test_long_format_temporal_pivots_by_category():
    rows = (
        [{"month": f"2024-0{m}", "channel": ch, "revenue": m * 10 + len(ch)}
         for m in range(1, 7) for ch in ("Store", "Web")]
    )
    hint = VizAgent().build_chart_hint("Revenue by month per channel", _result(rows))
    assert hint["kind"] == "line"
    assert hint["x"] == "month"
    assert hint["color"] == "channel"
    assert hint["y"] == ["revenue"]


def test_wide_temporal_without_nominal_unchanged():
    rows = [{"month": f"2024-0{m}", "revenue": m} for m in range(1, 5)]
    hint = VizAgent().build_chart_hint("Revenue by month", _result(rows))
    assert hint["kind"] == "line"
    assert "color" not in hint


def test_bar_top_n_only_when_many_groups():
    few = [{"cat": f"c{i}", "v": i} for i in range(8)]
    many = [{"cat": f"c{i}", "v": i} for i in range(30)]
    a = VizAgent()
    assert "top_n" not in (a.build_chart_hint("value by cat", _result(few)) or {})
    hint = a.build_chart_hint("value by cat", _result(many))
    assert hint["top_n"] == 12


def test_scatter_needs_enough_points_else_kpi():
    a = VizAgent()
    small = [{"x": i, "y": i * 2} for i in range(4)]
    big = [{"x": i, "y": i * 2} for i in range(12)]
    assert a.build_chart_hint("x vs y", _result(small))["kind"] == "kpi"
    assert a.build_chart_hint("x vs y", _result(big))["kind"] == "scatter"


def test_pie_still_gated_small_positive_groups():
    rows = [{"region": r, "share": i + 1} for i, r in enumerate(["N", "S", "E", "W"])]
    hint = VizAgent().build_chart_hint("share by region", _result(rows))
    assert hint["kind"] == "pie"
    assert hint["sort"] == "desc"
