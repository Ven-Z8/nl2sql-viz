"""VizAgent — picks a chart hint for the frontend from query results.

Fully deterministic (no LLM call): the server knows the result's column
shapes, so chart selection is a pure function of (question, result, query
type). The frontend renders bar/line/area/pie/scatter/histogram/kpi itself;
the server only decides WHICH chart and WHICH columns.

Emitted shape (shared WS contract):
    {"kind": "bar"|"stacked_bar"|"grouped_bar"|"line"|"area"|"pie"|"scatter"|
             "histogram"|"kpi",
     "x": str | None,
     "y": list[str],
     "color": str | None,      # series dimension for stacked/grouped bars
     "title": str | None,
     "limit_applied": int | None}
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.models import QueryResult, QueryType

# Rows above this count are downsampled by the caller before charting;
# limit_applied tells the frontend the data was capped.
CHART_POINT_LIMIT = 1_000

_PIE_MAX_GROUPS = 6
# A second categorical with more distinct values than this makes a hopeless
# stacked bar — fall back to the plain single-measure chart instead.
_STACKED_MAX_SERIES = 8
# Beyond this many categories a bar chart becomes a wall — the hint carries
# top_n so the renderer shows only the leading slices (sorted desc).
_BAR_MAX_GROUPS = 12

_DISTRIBUTION_HINTS = re.compile(
    r"\b(distribution|histogram|spread of|range of|frequency of)\b", re.IGNORECASE
)
# datetime.fromisoformat rejects reduced-precision ISO dates ("2024", "2024-01")
# yet month/year grain is everywhere in real aggregates.
_DATE_LIKE = re.compile(
    r"^\d{4}(?:-\d{1,2}){0,2}(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?(?:Z|[+-]\d{2}:?\d{2})?$"
)
_YEAR_FIELD = re.compile(r"(^|_)(year|yr)(_|$)", re.IGNORECASE)


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float, Decimal)) and not isinstance(v, bool)


def _is_temporal(v: Any) -> bool:
    if isinstance(v, (date, datetime)):
        return True
    if isinstance(v, str):
        s = v.strip()
        if _DATE_LIKE.match(s):
            return True
        try:
            datetime.fromisoformat(s.replace("Z", "+00:00"))
            return True
        except ValueError:
            return False
        except TypeError:
            return False
    return False


def _year_column(field: str, rows: list[dict]) -> bool:
    """Integer columns named *year* whose values plausibly are years."""
    if not _YEAR_FIELD.search(field):
        return False
    vals = [r.get(field) for r in rows if r.get(field) is not None]
    return bool(vals) and all(
        _is_number(v) and 1500 <= float(v) <= 2200 for v in vals
    )


def _primary_measure(question: str | None, numeric: list[str]) -> str:
    """The measure the question actually asks about (token overlap scoring).

    "How does median income vary across states?" over measures
    [median_income, avg_county_income, ...] picks median_income — plotting
    every aggregate column as side-by-side bars is noise, not insight.
    """
    if len(numeric) == 1:
        return numeric[0]
    q_tokens = set(re.findall(r"[a-z]+", (question or "").lower()))
    best, best_score = numeric[0], -1
    for field in numeric:
        score = sum(
            1 for tok in re.findall(r"[a-z]+", field.lower())
            if len(tok) > 2 and tok in q_tokens
        )
        if score > best_score:
            best, best_score = field, score
    return best


class VizAgent:
    """Deterministic chart-hint planner (no LLM needed — data shape suffices)."""

    def build_chart_hint(
        self,
        question: str,
        result: QueryResult,
        query_type: QueryType | None = None,
    ) -> dict[str, Any] | None:
        """Pick a chart deterministically from result shape + question intent."""
        if not result.rows:
            return None

        fields = list(result.rows[0].keys())
        numeric = [
            f for f in fields
            if all(_is_number(r.get(f)) for r in result.rows if r.get(f) is not None)
            and not _year_column(f, result.rows)
        ]
        temporal = [
            f for f in fields
            if f not in numeric and (
                _year_column(f, result.rows)
                or all(
                    _is_temporal(r.get(f)) for r in result.rows if r.get(f) is not None
                )
            )
        ]
        nominal = [f for f in fields if f not in numeric and f not in temporal]

        def _hint(
            kind: str, x: str | None, y: list[str], color: str | None = None,
            top_n: int | None = None,
        ) -> dict[str, Any]:
            hint: dict[str, Any] = {
                "kind": kind,
                "x": x,
                "y": y[:4],
                "title": question or None,
                "limit_applied": CHART_POINT_LIMIT if result.row_count > CHART_POINT_LIMIT else None,
                # Renderers sort categorical charts desc by their first measure;
                # keeps unsorted SQL from producing random-looking bars.
                "sort": "desc" if kind in {"bar", "pie", "stacked_bar", "grouped_bar"} else None,
            }
            if color is not None:
                # Series dimension — stacked/grouped bars, or the pivot column
                # that splits a temporal line/area into one series per value.
                hint["color"] = color
            if top_n is not None:
                hint["top_n"] = top_n
            return hint

        # 1. KPI — single-row metric sets render as stat tiles
        if len(result.rows) == 1 and numeric:
            return _hint("kpi", None, numeric)

        # 2. Temporal x → line/area time series.
        # Long format (month, channel, revenue): pivot on the nominal column
        # so each category becomes its own series instead of being ignored.
        if temporal:
            t = temporal[0]
            series = [f for f in numeric if f != t]
            if (
                len(nominal) >= 1 and len(series) == 1
                and 2 <= len({r.get(nominal[0]) for r in result.rows}) <= _STACKED_MAX_SERIES
            ):
                return _hint("line", t, series, color=nominal[0])
            return _hint("line", t, series or numeric)

        # 3. Distribution queries over a single numeric measure → histogram
        if (
            query_type == QueryType.DISTRIBUTION or _DISTRIBUTION_HINTS.search(question or "")
        ) and len(numeric) >= 1 and nominal:
            return _hint("histogram", nominal[0], [])

        # 4. Categorical x + numeric y → stacked/grouped variants, then pie/bar
        if nominal and numeric:
            groups = {r.get(nominal[0]) for r in result.rows}
            n_groups = len(groups)
            primary = _primary_measure(question, numeric)
            # Multiple measures per category → side-by-side bars, but only
            # when both stay small; otherwise plot just the asked-about one.
            if len(numeric) >= 2:
                if len(numeric) <= 3 and n_groups <= _BAR_MAX_GROUPS:
                    return _hint("grouped_bar", nominal[0], numeric, top_n=_BAR_MAX_GROUPS if n_groups > 8 else None)
                return _hint("bar", nominal[0], [primary], top_n=_BAR_MAX_GROUPS if n_groups > _BAR_MAX_GROUPS else None)
            # One measure + a second categorical → stacked by that series
            if len(nominal) >= 2:
                series_values = {r.get(nominal[1]) for r in result.rows}
                if 2 <= len(series_values) <= _STACKED_MAX_SERIES:
                    return _hint("stacked_bar", nominal[0], [numeric[-1]], color=nominal[1])
            if 2 <= n_groups <= _PIE_MAX_GROUPS:
                return _hint("pie", nominal[0], [primary])
            return _hint(
                "bar", nominal[0], [primary],
                top_n=_BAR_MAX_GROUPS if n_groups > _BAR_MAX_GROUPS else None,
            )

        # 5. Two numeric columns, nothing categorical → scatter (needs enough
        # points to show a relationship; a handful is just noise)
        if len(numeric) >= 2:
            if len(result.rows) >= 8:
                return _hint("scatter", numeric[0], [numeric[1]])
            return _hint("kpi", None, numeric)

        # 6. Fallback — first field on x, best numeric on y
        x_field = fields[0]
        return _hint("bar", x_field, [f for f in numeric if f != x_field])
