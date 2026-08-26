# NL2SQL Viz

Natural-language analytics copilot for Postgres databases. Users ask business questions in plain English, get guarded SQL queries, and see results as interactive charts.

## Language

**Query**:
A user's natural-language question about their data, transformed into a safe SQL statement.
_Avoid_: Prompt, request, question

**Connection**:
A user's authenticated link to a specific Postgres database, identified by a deterministic hash of its DSN.
_Avoid_: Database, data source, datasource

**Schema Map**:
A compact text representation of a database's tables, columns, types, and relationships — sized to fit in an LLM context window.
_Avoid_: Schema dump, DDL, metadata

**Result Set**:
The rows returned by a guarded SQL execution, bounded by the Query Engine's size-aware strategies.
_Avoid_: Dataset, data, response

**Chart Hint**:
A lightweight instruction emitted by the VizAgent telling the client _which_ chart to draw: `{kind, x, y, title, limit_applied}` where kind ∈ bar|line|area|pie|scatter|histogram|kpi. The frontend's single DataChart component renders it with the result rows (ADR-0004).
_Avoid_: Chart Spec, Vega-Lite spec, ECharts option, Visualization, chart, graph

**SQL Guard**:
The multi-layer safety system that validates generated SQL before execution — syntax check, cost estimation, timeout enforcement.
_Avoid_: Validator, filter, sanitizer

**Analytics Pipeline**:
The end-to-end flow: Schema → SQL → (optional Transform) → Visualization. Orchestrated by the Coordinator.
_Avoid_: Workflow, DAG, pipeline

**Analytics Copilot UI**:
A three-layer interactive experience: (1) smart auto-selected charts, (2) dashboard-style filters and drill-down, (3) conversational follow-up questions that morph the chart in place. All three layers ship in V1.
_Avoid_: Dashboard, BI tool, analytics app

**Thread**:
Short-term per-user conversational memory that lets a follow-up question resolve pronouns and ellipsis against prior turns. Each turn stores the question, the SQL that ran, row count, a compact result summary (columns + example values, never full rows), and the tables touched. In-memory only; bounded by 20 turns/thread, 50 threads/user (LRU), and a 30-min idle TTL. A foreign thread*id is indistinguishable from an unknown one — it silently starts a fresh thread.
\_Avoid*: Chat history, session, conversation ID

**Refine Loop**:
The execute-inspect-refine self-correction pass: after execution, the result set is inspected for quality signals (zero rows, degenerate aggregate, null-dominant columns, uniform values) and the SQL is regenerated with that feedback before synthesis. Bounded by the shared execution budget of 4 per question, with at most 2 refine iterations.
_Avoid_: Retry, self-heal, repair

**Cost Tighten**:
The deterministic ladder of SQL rewrites applied when EXPLAIN cost exceeds MAX*COST — no extra LLM calls: attempt 1 caps output rows with a LIMIT (proportional to budget, ≥200 floor); attempt 2 narrows ISO-date BETWEEN windows to their recent half, falling back to dropping a planner-marked `optional_join`. Tightenings stack across attempts.
\_Avoid*: Query optimization, cost reduction

**Provenance Entry**:
The wire-shape trace tying one cited answer number back to its source: `{label, value, query_index, row_index}` into the shipped result set. Metrics without a matching trace are dropped from answers rather than shown ungrounded.
_Avoid_: Citation, source map

## Scope

- **V1 target**: Postgres 1M–5M rows, full NOOA architecture, 3-layer copilot UI, deployed to public URL
- **Architecture must allow**: future scale to 100M+ rows and additional backends (DuckDB, ClickHouse)
- **Deployment**: Vercel (Next.js frontend) + Railway (FastAPI backend + Postgres)
- **Demo flow**: Instant demo with RavenStack synthetic data + "Connect your database" option
- **Code execution**: out of scope for V1 (CodeAct scaffolding removed 2026-08-25; revisit post-deployment if needed)
- **Testing**: Parallel testing — old + new tests side by side during migration
- **Out of scope for V1**: Data lake federation, Spark connectors, multi-tenant SaaS, V2/V3 scope open
