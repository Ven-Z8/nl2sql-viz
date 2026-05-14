import json

from app.agents.chart_planner import build_chart_spec


def test_build_chart_spec_creates_grouped_time_series_line_chart() -> None:
    rows = [
        {"month": "2024-01-01", "plan_tier": "Basic", "mrr": 1200.0},
        {"month": "2024-01-01", "plan_tier": "Pro", "mrr": 3200.0},
        {"month": "2024-02-01", "plan_tier": "Basic", "mrr": 1500.0},
    ]

    spec = json.loads(
        build_chart_spec(
            nl_query="Show monthly recurring revenue by plan tier over time.",
            rows=rows,
        )
    )

    assert spec["mark"]["type"] == "line"
    assert spec["width"] == 760
    assert spec["height"] == 360
    assert spec["background"] == "transparent"
    assert spec["encoding"]["x"]["field"] == "month"
    assert spec["encoding"]["x"]["type"] == "temporal"
    assert spec["encoding"]["y"]["field"] == "mrr"
    assert spec["encoding"]["color"]["field"] == "plan_tier"


def test_build_chart_spec_creates_category_bar_chart() -> None:
    rows = [
        {"region": "North", "total": 2500.0},
        {"region": "South", "total": 2000.0},
    ]

    spec = json.loads(build_chart_spec(nl_query="Total sales by region", rows=rows))

    assert spec["mark"]["type"] == "bar"
    assert spec["width"] == 760
    assert spec["height"] == 360
    assert spec["encoding"]["x"]["field"] == "region"
    assert spec["encoding"]["y"]["field"] == "total"
    assert spec["config"]["axis"]["labelColor"] == "#cbd5e1"


def test_build_chart_spec_returns_none_for_empty_rows() -> None:
    assert build_chart_spec(nl_query="Nothing", rows=[]) is None
