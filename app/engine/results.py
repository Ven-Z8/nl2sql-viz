"""Result size management — size-aware strategies for query results.

Decides how to handle query results based on row count:
- INLINE: ≤1K rows, send as-is
- SAMPLED: 1K–100K rows, stratified downsample
- AGGREGATED: 100K+ rows, compute statistical summary
"""

from __future__ import annotations

import random
import statistics
from typing import Any

from app.models import DataStrategy, QueryResult

INLINE_LIMIT = 1_000
SAMPLE_LIMIT = 100_000


def classify_size(result: QueryResult) -> DataStrategy:
    """Determine the data delivery strategy based on row count."""
    if result.row_count <= INLINE_LIMIT:
        return DataStrategy.INLINE
    if result.row_count <= SAMPLE_LIMIT:
        return DataStrategy.SAMPLED
    return DataStrategy.AGGREGATED


def stratified_sample(rows: list[dict[str, Any]], target: int) -> list[dict[str, Any]]:
    """Downsample rows preserving distribution across the first dimension."""
    if len(rows) <= target:
        return rows

    # Systematic sampling: pick every Nth row starting from a random offset
    step = len(rows) / target
    offset = random.random() * step
    indices = [int(offset + i * step) for i in range(target)]
    return [rows[i] for i in indices if i < len(rows)]


def compute_summary_stats(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Compute statistical summary for numeric columns."""
    if not rows:
        return {}

    stats: dict[str, dict[str, float]] = {}
    for field in rows[0]:
        values = [r[field] for r in rows if isinstance(r.get(field), (int, float))]
        if len(values) < 2:
            continue
        stats[field] = {
            "count": len(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
        }
    return stats


def prepare_for_viz(result: QueryResult) -> tuple[DataStrategy, list[dict[str, Any]], dict[str, Any]]:
    """Prepare query results for visualization.

    Returns: (strategy, data_for_chart, metadata)
    """
    strategy = classify_size(result)

    if strategy == DataStrategy.INLINE:
        return strategy, result.rows, {"original_count": result.row_count}

    if strategy == DataStrategy.SAMPLED:
        sampled = stratified_sample(result.rows, INLINE_LIMIT)
        return strategy, sampled, {
            "original_count": result.row_count,
            "sampled_count": len(sampled),
        }

    # AGGREGATED: return summary statistics instead of raw rows
    summary = compute_summary_stats(result.rows)
    return strategy, [], {
        "original_count": result.row_count,
        "summary_stats": summary,
    }
