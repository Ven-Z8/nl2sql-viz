"""Query cost estimator — pre-execution cost analysis using EXPLAIN.

FAIL-CLOSED: if EXPLAIN is unavailable or errors out, the query is reported
as UNSAFE so the pipeline blocks it instead of executing blind. Queries whose
estimated row scan or planner cost exceeds the configured limits are also
rejected with an actionable reason.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from app.db.pool import PostgresPool
from app.models import QueryCost

logger = logging.getLogger(__name__)

# Configurable thresholds
MAX_ESTIMATED_ROWS = 10_000_000  # 10M row scan limit
MAX_COST = float(os.getenv("MAX_COST", "100000"))  # PostgreSQL cost units


async def estimate_cost(pool: PostgresPool, sql: str) -> QueryCost:
    """Run EXPLAIN and return structured cost information.

    Fail-closed contract: any error producing an estimate returns
    ``is_safe=False`` so the caller blocks execution.
    """
    try:
        plan = await pool.explain(sql)
    except Exception as e:
        logger.warning("EXPLAIN failed — blocking query (fail-closed): %s", e)
        return QueryCost(
            estimated_rows=0,
            estimated_cost=0,
            is_safe=False,
            reason=(
                f"Cost estimate unavailable (EXPLAIN failed) — query blocked "
                f"for safety. Original error: {e}"
            ),
        )

    node = plan.get("Plan", {})
    estimated_rows = node.get("Plan Rows", 0)
    estimated_cost = node.get("Total Cost", 0)
    scan_type = node.get("Node Type", "Unknown")

    # Extract tables touched from relation nodes
    tables_touched = _extract_tables(node)

    cost = QueryCost(
        estimated_rows=estimated_rows,
        estimated_cost=estimated_cost,
        scan_type=scan_type,
        tables_touched=tables_touched,
    )

    # Gate checks — rows scanned, then planner cost units
    if estimated_rows > MAX_ESTIMATED_ROWS:
        cost.is_safe = False
        cost.reason = (
            f"Query would scan ~{estimated_rows:,.0f} rows "
            f"(limit: {MAX_ESTIMATED_ROWS:,}). "
            "Add WHERE filters, GROUP BY, or LIMIT."
        )
    elif estimated_cost > MAX_COST:
        cost.is_safe = False
        cost.reason = (
            f"Estimated query cost {estimated_cost:,.0f} exceeds the maximum "
            f"budget of {MAX_COST:,.0f}. Add WHERE filters or LIMIT."
        )

    return cost


def _extract_tables(node: dict[str, Any]) -> list[str]:
    """Walk the EXPLAIN plan tree and extract table names."""
    tables: list[str] = []
    if "Relation Name" in node:
        tables.append(node["Relation Name"])
    for child in node.get("Plans", []):
        tables.extend(_extract_tables(child))
    return list(set(tables))
