# NL2SQL Viz (DataLens AI) — Handover

> **Status: 2026-08-10 — user rates the project 2–2.5/5.** The SQL/grounding
> pipeline works (99% benchmark pass), but the *product* is not good enough:
> complex queries break, and answers are bare numbers with no story. This
> document tells a fresh agent exactly what the system is, how to run it, what
> is known to be broken, and what the user expects next.

---

## 1. What this project is

A natural-language analytics copilot: the user types a business question, the
system generates guarded SQL against a real Postgres database, executes it, and
returns a **grounded answer** (every number from real data — no hallucination)
plus a chart. Branded **DataLens AI**. It is the user's flagship portfolio
project for an AI-engineer job search.

**The user's stated goal:** *"prove my system can handle real very complex
questions and generate really great interactive 3d visualizations."*

**Hard user constraints (never violate):**
- **Never hardcode skills/metrics to data models** — domain skills must adapt
  to any schema. (This is why the "metric registry" idea was rejected in favor
  of a fast-model schema linker.)
- **No guessing** — the system must verify SQL against the real schema before
  executing (SchemaValidator).
- **Grounded answers only** — every number must trace to executed query results.

---

## 2. How to run

```bash
# Postgres (Docker)
docker compose up -d

# Backend (FastAPI + NOOA agents) — port 8000
uv run uvicorn app.main:app --port 8000 --host 0.0.0.0

# Frontend (Next.js 16) — port 3000
cd frontend && npm run dev

# Tests (121 passing)
uv run pytest tests -q

# Frontend typecheck
cd frontend && npx tsc --noEmit
```

**Environment:** `.env` needs `OPENROUTER_API_KEY`, `NL2SQL_MODEL`
(`openrouter/deepseek/deepseek-v4-flash-0731`), `NL2SQL_FAST_MODEL`
(`openrouter/inclusionai/ling-3.0-flash`). Models go through OpenRouter via
litellm — the `openrouter/` prefix is required.

**Datasets:** 12 loaded in Postgres (7 real: Olist, FDIC, GA bike-share, Census
ACS, TPC-DS, CMS, World Bank; 5 generated). CSVs are gitignored; `schema.json`
+ `questions.json` per dataset are committed. Reload any dataset with:
`uv run python -m scripts.load_dataset <id>`.

---

## 3. Architecture (the pipeline)

Every question flows through `CoordinatorAgent.run()` (`app/agents/coordinator.py`):

1. **Schema introspection** — `SchemaAgent.fetch_schema()` reads tables/columns
   from Postgres; scoped to the focus table's **FK-connected graph** (the
   selected dataset).
2. **Schema linking** — `SchemaLinker` (fast model, Ling flash) reads the
   question + dataset schema and returns the relevant tables/columns; the SQL
   model then generates against only that filtered context. **Note:** Ling
   flash rejects `json_schema` response format — the linker uses
   `json_object` + manual parsing (`app/agents/schema_linker.py`).
3. **Complexity routing** — `classify_complexity` (Predict) → simple (single
   query) vs complex (multi-query plan + report).
4. **SQL generation** — `SQLAgent.generate_simple` (Predict, DeepSeek flash)
   against the linked schema; complex path uses `plan_analysis` → parallel
   `generate_simple` via `asyncio.gather`.
5. **Schema validation** — `SchemaValidator` (sqlglot) verifies every column
   against the real schema; fixes typos/case mismatches (quotes uppercase
   columns), retries with feedback on unresolvable references.
6. **Execution** — read-only, cost-gated Postgres queries.
7. **Grounded answer** — `extract_metrics` + `build_answer`; complex questions
   synthesize multi-section reports (`ReportSection`).

**Key files:**
- `app/agents/coordinator.py` — orchestration, answer assembly
- `app/agents/schema_linker.py` — fast-model schema linking
- `app/agents/sql_agent.py` — SQL generation, planning, classification
- `app/agents/viz_agent.py` — chart planning (bar/line/scatter only)
- `app/core/schema_validator.py` — the "no guessing" gate
- `app/models.py` — Pydantic contracts (SchemaMap, GroundedAnswer, etc.)
- `app/main.py` — FastAPI + WebSocket
- `frontend/src/app/page.tsx`, `frontend/src/components/LeftPanel.tsx`,
  `frontend/src/components/RightPanel.tsx`, `frontend/src/components/VegaChart.tsx`
- `data/datasets/<id>/schema.json` + `questions.json` — 12 datasets
- `docs/architecture.md` — mermaid diagram
- `docs/benchmark-report.md` — last benchmark results

---

## 4. What works (evidence)

- **Benchmark (2026-08-10):** 138 questions across 12 datasets → **137 passed
  (99%)**. 11/12 datasets perfect; the single failure was an FDIC very-complex
  question whose planned queries returned zero rows. Report:
  `docs/benchmark-report.md`. Raw results: `data/benchmark/*.json`.
- **121 tests pass** (`uv run pytest tests -q`).
- Real databases load and join correctly (FKs verified).
- Two real bugs were found and fixed during benchmarking: validator
  case-sensitivity (uppercase columns must be quoted) and bare-column scoping
  (columns must exist in the query's FROM/JOIN tables).

---

## 5. Known gaps — why the user rates it 2–2.5/5

### 5.1 Complex queries break (the #1 complaint)
The user tried complex questions in the UI and **some broke**. The benchmark
pass rate (99%) measures "a result event arrived" — it does NOT measure whether
the answer is *correct* or *useful*. Known failure modes:
- **Zero-row results** — planned sub-queries can return empty (FDIC
  very-complex question failed this way).
- **Wrong-table selection** — the linker can pick a plausible-but-wrong table
  (e.g. `upload_retail_orders` instead of the selected dataset's tables) when
  no focus table is set; the validator then fuzzy-fixes columns to make the
  wrong query run.
- **Semantic wrongness** — e.g. World Bank questions average ALL indicators
  instead of filtering the right `indicator_code` (cryptic codes). The query
  runs, the number is wrong, the user sees a wrong answer with no warning.
- **Long tail latency** — very-complex questions can take 3–20+ minutes
  (model-bound; the 12-way parallel benchmark inflated this, but single-stream
  easy questions still median ~50s).

### 5.2 Answers are numbers, not a story (the #2 complaint)
`build_answer` produces `"Total Revenue: 16,008,872.12"` or a pipe-joined
metric list (`"Total X 123 | Latest X 456"`). The user wants:
- **Key points / a narrative** — what the numbers mean, the insight, the
  "so what" (e.g. "Revenue grew 18% YoY, driven by the electronics category in
  the South region").
- Complex questions already produce `ReportSection`s, but the sections are
  also bare metric lists (`"title: k=v, k=v"`), not prose.
- **The answer should read like an analyst's summary**, not a debug dump.

### 5.3 Latency
- Easy: median ~50s, p90 ~118s. Very-complex: median ~181s, p90 ~416s.
- Structural costs: `classify_complexity` runs on the SLOW model (DeepSeek)
  — should be the fast model; validation retries are sequential (each retry is
  a full regenerate); the linker adds ~5–11s per question.
- The user remembers "30s for very-complex" from a single-stream run before
  the 12-way parallel benchmark inflated numbers.

### 5.4 Visualization is basic
- Chart layer is deterministic bar/line/scatter only (Vega-Lite). No 3D, no
  heatmap, no maps, no ECharts (though `ChartSpec.renderer` anticipates
  `'echarts'`). The user's headline goal is "great interactive 3d
  visualizations" — this is the biggest unbuilt feature.
- `query_type` (KPI/TREND/COMPARISON/DISTRIBUTION/BREAKDOWN) is computed but
  never passed to `plan_chart` — chart choice is purely data-shape driven.

### 5.5 Question ladders were just redesigned (2026-08-10)
All 12 `questions.json` rewritten to analyst-intelligence questions that drive
charts (trends, comparisons, distributions, correlations, insight reports).
Frontend now groups them by difficulty tier. **These have NOT been re-benchmarked
or validated for answer correctness** — the user is testing them manually and
finding failures.

---

## 6. What the user expects next

1. **Complex queries must not break** — identify and fix the failures the
   user hits (the testing agent's job is to find them).
2. **Answers must tell a story** — grounded numbers PLUS key points / an
   analyst-style narrative. This is the highest-value product improvement.
3. **Latency down** — fast-model classification, fewer sequential retries,
   sensible caching.
4. **Eventually: 3D interactive visualizations** (ECharts GL) — the headline
   portfolio feature.

---

## 7. Test cases the next agent should run

The user will have another agent run tests and report failures. Give it this
checklist:

1. **Full suite:** `uv run pytest tests -q` (expect 121 passing).
2. **Frontend typecheck:** `cd frontend && npx tsc --noEmit`.
3. **Manual UI test** (servers running): load each dataset, click every
   question in the ladder, record: (a) did it produce a result or error?
   (b) is the answer *correct* (verify against the data)? (c) does the answer
   tell a story or just dump numbers? (d) how long did it take?
4. **Known-fragile questions to probe:**
   - World Bank: any question naming an indicator (life expectancy, GDP,
     internet usage) — check the SQL filters `indicator_code` correctly.
   - FDIC very-complex: "Compare 2020 vs 2024 profitability…" (previously
     returned zero rows).
   - Any very-complex question on a 24-table schema (TPC-DS).
   - Questions with no focus table (connect-your-own DSN path) — the linker
     sees all tables and can pick wrong ones.
5. **Benchmark re-run** (optional, slow): `uv run python -m scripts.benchmark
   <dataset> 10` per dataset, then `uv run python -m scripts.benchmark_report`.
   Note: the script is resumable; the monitor tool kills idle processes, so
   expect to re-run.

**Report format the user wants:** a list of failing test cases with the exact
question, the error/behavior, and what the correct behavior should be.

---

## 8. Quick reference

- **Benchmark runner:** `uv run python -m scripts.benchmark <dataset_id> [delay] [limit]`
- **Report generator:** `uv run python -m scripts.benchmark_report`
- **Dataset loader:** `uv run python -m scripts.load_dataset <id>`
- **Question validation:** `uv run python -m scripts.validate_questions`
- **LLM config:** `app/llm.py` (SONNET = DeepSeek flash, HAIKU = Ling flash)
- **Domain skills:** `app/skills/` (SKILL.md bundles, injected as analyst
  guidance into SQL generation)
- **Docs:** `docs/architecture.md`, `docs/benchmark-report.md`,
  `docs/nl2sql-enterprise-research.md` (semantic-layer research — the
  "column descriptions" and "few-shot examples" items are still unbuilt and
  would fix the World Bank indicator problem)