# Server sends chart hints; a single client-side renderer draws them

**Date:** 2026-08-25 · **Status:** Accepted · **Supersedes:** [ADR-0003](0003-echarts-for-large-interactive-charts.md)

## Context

The backend previously generated full Vega-Lite specifications intended for a
dual-engine frontend (Vega-Lite + ECharts). Audit found **zero consumers**: the
frontend ignored `chart_spec`, re-picked chart kinds client-side via fragile
heuristics (e.g. date-sniffing any parseable string column), and rendered with
Recharts. Docs described an unbuilt system, and chart selection lived on the
side with the least information about the query.

## Decision

1. **Server is the source of truth for *which* chart** — it knows the question,
   schema types, and result shape. The agent emits a lightweight hint instead of
   a rendering spec:

   ```json
   {
     "kind": "bar|line|area|pie|scatter|histogram|kpi",
     "x": "<column> | null",
     "y": ["<column>", ...],
     "title": "<question>",
     "limit_applied": null | <int>
   }
   ```

   Selection rules: `kpi` for single-row metric sets, `line`/`area` for temporal
   x, `pie` for ≤6 categorical groups, `scatter` for two numeric columns,
   `histogram` for single-column distributions, `bar` otherwise.

2. **One client renderer** (`components/DataChart.tsx`, Recharts) consumes the
   hint and rows — replacing five near-identical wrapper components. The client
   bins histograms locally and shows an honest truncation badge when
   `rows.length < row_count`.

3. **No new frontend charting dependency.** ECharts/ECharts GL remain a *future*
   option for 3D visualizations; adopting them later means adding a renderer
   behind the same hint contract, not re-plumbing the pipeline.

## Consequences

- Kills the date-sniffing misfires and dead payload bytes.
- Backend bundle of chart logic stays deterministic and testable.
- If pixel-exact declarative rendering is ever needed, the hint can be upgraded
  to a full spec without changing the transport contract.
