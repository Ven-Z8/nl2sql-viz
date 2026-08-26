# Use ECharts alongside Vega-Lite for interactive charts at scale

> **Status: Superseded by [ADR-0004](0004-server-chart-hints-single-renderer.md) (2026-08-25).**
> This dual-engine design was never implemented — no frontend code ever consumed
> Vega-Lite or ECharts payloads from the backend. Retained for decision history.

ECharts (Apache) is the primary charting library for large, interactive visualizations. Vega-Lite is retained for small result sets (≤50K rows) where its declarative grammar-of-graphics approach is faster to generate. ECharts handles 100K+ data points via Canvas rendering and millions via WebGL, with built-in LTTB downsampling and `dataZoom` filtering.

**Considered Options:**

- **ECharts** (chosen) — 100K+ points, ~100KB tree-shaken, battle-tested at Alibaba/Tencent/AWS
- **Plotly.js** — performance issues at scale (browser freezes, hover lag), 430KB+ bundle
- **deck.gl** — designed for geospatial data, wrong tool for standard analytics charts
- **Vega-Lite only + server aggregation** — viable but less interactive out-of-the-box
- **Apache Superset** — full BI platform requiring separate infrastructure, not a library

**Why ECharts:** It covers the full range from small bar charts to 100K+ point scatter plots in one library. Tree-shaking keeps the bundle at ~100KB. The config-driven API is easy to generate from a backend agent (similar structure to Vega-Lite JSON). Built-in progressive rendering and `dataZoom` give users interactive filtering without custom code.

**Consequences:** Two charting libraries in the frontend. The VizAgent must output either Vega-Lite JSON or ECharts option objects based on the data tier. A `<ChartRenderer>` component switches between them. ECharts requires a custom React wrapper component (no official React package).
