import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

_VEGA_SCHEMA = "https://vega.github.io/schema/vega-lite/v6.json"


def _base_spec(title: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "$schema": _VEGA_SCHEMA,
        "title": {
            "text": title,
            "color": "#e5e7eb",
            "fontSize": 15,
            "anchor": "start",
        },
        "background": "transparent",
        "width": 760,
        "height": 360,
        "autosize": {"type": "fit", "contains": "padding"},
        "data": {"values": rows},
        "config": {
            "axis": {
                "labelColor": "#cbd5e1",
                "titleColor": "#94a3b8",
                "gridColor": "#1f2937",
                "domainColor": "#334155",
                "tickColor": "#334155",
            },
            "legend": {
                "labelColor": "#cbd5e1",
                "titleColor": "#94a3b8",
                "orient": "bottom",
            },
            "view": {"stroke": "transparent"},
        },
    }


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float | Decimal) and not isinstance(value, bool)


def _is_temporal(value: Any) -> bool:
    if isinstance(value, date | datetime):
        return True
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value[:10])
        return True
    except ValueError:
        return False


def _fields_by_type(rows: list[dict[str, Any]]) -> tuple[list[str], list[str], list[str]]:
    fields = list(rows[0].keys())
    numeric: list[str] = []
    temporal: list[str] = []
    nominal: list[str] = []

    for field in fields:
        values = [row.get(field) for row in rows if row.get(field) is not None]
        if not values:
            continue
        if all(_is_number(value) for value in values):
            numeric.append(field)
        elif all(_is_temporal(value) for value in values):
            temporal.append(field)
        else:
            nominal.append(field)

    return numeric, temporal, nominal


def build_chart_spec(nl_query: str, rows: list[dict[str, Any]]) -> str | None:
    """Build a deterministic Vega-Lite spec for common BI result shapes."""
    if not rows:
        return None

    numeric, temporal, nominal = _fields_by_type(rows)
    if not numeric:
        return None

    title = nl_query.strip().rstrip(".") or "Query results"
    y_field = numeric[-1]

    if temporal:
        spec = _base_spec(title, rows)
        spec.update({
            "mark": {
                "type": "line",
                "point": {"filled": True, "size": 48},
                "tooltip": True,
                "strokeWidth": 2.5,
            },
            "encoding": {
                "x": {
                    "field": temporal[0],
                    "type": "temporal",
                    "title": temporal[0],
                    "axis": {"labelAngle": 0},
                },
                "y": {"field": y_field, "type": "quantitative", "title": y_field},
                "tooltip": [{"field": field} for field in rows[0].keys()],
            },
        })
        if nominal:
            spec["encoding"]["color"] = {
                "field": nominal[0],
                "type": "nominal",
                "title": nominal[0],
            }
        return json.dumps(spec, default=_json_default)

    if nominal:
        spec = _base_spec(title, rows)
        spec.update({
            "mark": {"type": "bar", "tooltip": True},
            "encoding": {
                "x": {
                    "field": nominal[0],
                    "type": "nominal",
                    "title": nominal[0],
                    "sort": "-y",
                    "axis": {"labelAngle": -35},
                },
                "y": {"field": y_field, "type": "quantitative", "title": y_field},
                "tooltip": [{"field": field} for field in rows[0].keys()],
            },
        })
        return json.dumps(spec, default=_json_default)

    if len(numeric) >= 2:
        spec = _base_spec(title, rows)
        spec.update({
            "mark": {"type": "point", "tooltip": True},
            "encoding": {
                "x": {"field": numeric[0], "type": "quantitative", "title": numeric[0]},
                "y": {"field": numeric[1], "type": "quantitative", "title": numeric[1]},
                "tooltip": [{"field": field} for field in rows[0].keys()],
            },
        })
        return json.dumps(spec, default=_json_default)

    return None
