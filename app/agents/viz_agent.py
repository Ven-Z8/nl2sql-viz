"""VizAgent — generates chart specifications from query results.

NOOA Agent using PredictStrategy for single-shot chart spec generation.
Deterministic helpers handle chart type selection and data strategy routing.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from nooa import Agent, strategy
from nooa.strategies import PredictStrategy

from app.engine.results import classify_size, prepare_for_viz
from app.llm import SONNET
from app.models import (
    ChartPlan,
    ChartSpec,
    ChartType,
    QueryResult,
)


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float, Decimal)) and not isinstance(v, bool)


def _is_temporal(v: Any) -> bool:
    if isinstance(v, (date, datetime)):
        return True
    if not isinstance(v, str):
        return False
    try:
        date.fromisoformat(v[:10])
        return True
    except ValueError:
        return False


class VizAgent(Agent, llm=SONNET):
    """You are a data visualization expert. Given query results and the original
    question, you generate appropriate chart specifications.

    You have deterministic helpers:
    - self.plan_chart(question, result): analyzes data shape and picks chart type
    - self.build_vega_lite(plan, result): builds a Vega-Lite v5 spec
    """

    # ------------------------------------------------------------------
    # Deterministic helpers
    # ------------------------------------------------------------------

    def plan_chart(self, question: str, result: QueryResult) -> ChartPlan:
        """Analyze data shape and determine chart type and data strategy."""
        strategy = classify_size(result)

        if not result.rows:
            return ChartPlan(
                chart_type=ChartType.BAR,
                data_strategy=strategy,
                title=question,
            )

        fields = list(result.rows[0].keys())
        numeric = [f for f in fields if all(_is_number(r.get(f)) for r in result.rows if r.get(f) is not None)]
        temporal = [f for f in fields if all(_is_temporal(r.get(f)) for r in result.rows if r.get(f) is not None)]
        nominal = [f for f in fields if f not in numeric and f not in temporal]

        if temporal and numeric:
            return ChartPlan(
                chart_type=ChartType.LINE,
                data_strategy=strategy,
                title=question,
                x_field=temporal[0],
                y_field=numeric[-1],
                color_field=nominal[0] if nominal else "",
            )
        if nominal and numeric:
            return ChartPlan(
                chart_type=ChartType.BAR,
                data_strategy=strategy,
                title=question,
                x_field=nominal[0],
                y_field=numeric[-1],
            )
        if len(numeric) >= 2:
            return ChartPlan(
                chart_type=ChartType.SCATTER,
                data_strategy=strategy,
                title=question,
                x_field=numeric[0],
                y_field=numeric[1],
            )
        return ChartPlan(
            chart_type=ChartType.BAR,
            data_strategy=strategy,
            title=question,
            x_field=fields[0] if fields else "",
            y_field=numeric[-1] if numeric else "",
        )

    def build_vega_lite(self, plan: ChartPlan, result: QueryResult) -> ChartSpec:
        """Build a Vega-Lite v5 spec from a chart plan and data."""
        data_strategy, data, meta = prepare_for_viz(result)

        spec: dict[str, Any] = {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "title": {"text": plan.title, "color": "#e5e7eb", "fontSize": 15, "anchor": "start"},
            "background": "transparent",
            "width": 760,
            "height": 360,
            "autosize": {"type": "fit", "contains": "padding"},
            "data": {"values": data},
            "config": {
                "axis": {"labelColor": "#cbd5e1", "titleColor": "#94a3b8", "gridColor": "#1f2937"},
                "legend": {"labelColor": "#cbd5e1", "titleColor": "#94a3b8", "orient": "bottom"},
                "view": {"stroke": "transparent"},
            },
        }

        mark_map = {
            ChartType.LINE: {"type": "line", "point": {"filled": True, "size": 48}, "strokeWidth": 2.5},
            ChartType.BAR: {"type": "bar"},
            ChartType.SCATTER: {"type": "point", "size": 60},
            ChartType.ARC: {"type": "arc"},
        }
        spec["mark"] = mark_map.get(plan.chart_type, {"type": "bar"})

        encoding: dict[str, Any] = {}
        if plan.x_field:
            x_type = "temporal" if (data and _is_temporal(data[0].get(plan.x_field))) else "nominal"
            encoding["x"] = {"field": plan.x_field, "type": x_type, "title": plan.x_field}
        if plan.y_field:
            encoding["y"] = {"field": plan.y_field, "type": "quantitative", "title": plan.y_field}
        if plan.color_field:
            encoding["color"] = {"field": plan.color_field, "type": "nominal", "title": plan.color_field}
        encoding["tooltip"] = [{"field": f} for f in (data[0].keys() if data else [])]
        spec["encoding"] = encoding

        return ChartSpec(
            renderer="vega-lite",
            spec=spec,
            plan=plan,
            row_count=result.row_count,
        )

    # ------------------------------------------------------------------
    # Generation method — LLM picks chart type for ambiguous data
    # ------------------------------------------------------------------

    @strategy(PredictStrategy())
    async def suggest_chart(self, question: str, column_names: str, sample_row: str) -> ChartPlan:
        """Given the question, column names, and a sample row, suggest the best chart type
        and encoding. Return a ChartPlan with chart_type, x_field, y_field, and color_field.

        Choose from: bar, line, scatter, arc, heatmap, summary
        Prefer line for temporal data, bar for categorical, scatter for two numeric fields."""
        ...
