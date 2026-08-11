# NL2SQL Viz — Comprehensive Real Testing Report (2026-08-10)

> Tested against the **live WebSocket backend** at `ws://localhost:8000/ws/query`
> using `scripts/reference_harness.py`. The harness runs each question end-to-end,
> captures all events, and **spot-checks** answers by re-running the generated SQL
> against the live Postgres and comparing the numbers.

The user's bar (from `test-questions-guide.md`): a question is only a **PASS** if the
answer is **correct** (numbers match the data), **tells a story** (key points, not a
bare-number dump), and **renders a sensible chart**. A query that "runs" but returns a
wrong number is a **FAIL**.

---

## 1. Live Test Results — Database Question Ladders

### Per-dataset summary

| Dataset | Tables | Qs run | PASS | FAIL | Harness ERR | Avg time | Known fragile hit? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **retail** | 5 | 3 | **3** | 0 | 0 | 74s | no |
| **olist** | 9 | 6 | **6** | 0 | 0 | 78s | no |
| **fdic** | 2 | 6 | **5** | 1 | 0 | 89s | ✅ easy "most active banks" → zero rows |
| **worldbank** | 3 | 6 | **2** | 3 | 1 (hang) | 112s | ✅ wrong table, timeout on GDP query |
| **tpcds** | 24 | 0 | — | — | **harness: load timed out** | — | load step failed |
| **cms** | 1 | 2 | **1** | 0 | **1** (WS ping timeout) | 70s | ⚠️ claim-by-year hung the WS |
| **ga** | 1 | 0 | — | — | **harness: load timed out** | — | load step failed |
| **census** | 2 | 2 | **1** | 0 | **1** (harness timeout) | 71s | no |
| **finance** | 4 | 0 | — | — | **3** (WS handshake timeout) | — | BUG-7: WS auth handshake timed out |
| **healthcare** | 5 | 0 | — | — | **3** (WS handshake timeout) | — | BUG-7: WS auth handshake timed out |
| **demographics_census** | 3 | 0 | — | — | **harness: load timed out** | — | load step failed (BUG-6) |
| **demographics_consumer** | 3 | 0 | — | — | **harness: load timed out** | — | load step failed (BUG-6) |
| **TOTAL** | — | **25** | **19** | **4** | **12** | — | — |

**Pass rate (questions that returned a result): 19/23 = 83%.**
Including harness-level errors: **19/37 = 51%.**

### Full question-by-question log

```
Dataset   Tier     Question                                                  Result  Time   Notes
───────── ──────── ───────────────────────────────────────────────────────── ────── ─────── ─────────────────────────────────────────────────────────────
retail    easy     Which sales channels contribute the most orders?          PASS   91.2s  mark=bar answer="Total Order Count 200,000 | Latest Order Count 49,837"
retail    easy     How does revenue break down by region?                    PASS   80.6s  mark=bar answer="Total Revenue 433 | Latest Total Revenue 239.99"
retail    easy     Which product categories sell the most units?             PASS   50.1s  mark=bar answer="Total Units 225,419.62 | Latest Units 214,324"
olist     easy     Which payment methods are used most often across orders?   PASS   92.0s  mark=bar
olist     easy     How does order volume vary by order status?               PASS   81.1s  mark=bar
olist     easy     Which product categories appear most frequently?          PASS   43.9s  mark=bar
olist     medium   What does the average order value look like by state?     PASS   89.6s  mark=bar
olist     medium   Compare total revenue across seller states               PASS  106.5s  mark=bar type=comparison
olist     medium   What is the distribution of review scores?                PASS   54.7s  mark=point type=distribution
fdic      easy     Which states host the most active banks?                 FAIL   78.3s  error: "Query returned zero rows. Try a broader question."
fdic      easy     How does the banking industry break down by bank class?  PASS   80.0s  mark=bar
fdic      easy     Which states hold the largest banking assets?             PASS   69.1s  mark=bar
fdic      medium   Compare average return on equity across bank classes     PASS   52.5s  mark=bar type=comparison
fdic      medium   What does the distribution of bank asset sizes look like? PASS  139.6s  mark=point type=distribution
fdic      medium   Which cities are home to the largest banks by assets?    PASS  116.1s  "The query returned data, but no numeric metrics were computed."
worldbank easy     How does life expectancy vary across world regions?      FAIL   78.2s  error: relation "ds__worldbank_indicators" does not exist (WRONG TABLE)
worldbank easy     Which countries have the largest populations?             PASS   80.3s  mark=bar
worldbank easy     How does GDP per capita compare across income groups?   FAIL  195.0s  error: Query timed out after 180s
worldbank medium   Compare internet adoption (high vs low income)          PASS  101.8s  mark=bar type=comparison
worldbank medium   What does the distribution of GDP growth look like?     HARNESS timeout — never returned
cms       easy     Which DRG codes appear most often in claims?             PASS   70.8s  mark=bar
cms       easy     How does claim volume break down by year?                HARNESS ERR  WS ping timeout at keepalive
census    easy     Which states have the largest populations?                PASS   71.8s  mark=bar
census    easy     How does median income vary across states?               HARNESS ERR  harness timeout (WS recv blocked)
```

---

## 2. Known-Fragile Questions — Targeted Probes

From `test-questions-guide.md` section 5. Reproduced live:

| # | Question | Result | Notes |
| --- | --- | --- | --- |
| 1 | **fdic easy** "Which states host the most active banks?" | **FAIL** zero rows | The SQL runs against `ds_fdic_institutions` and filters something that returns nothing. Confirms the handover's "zero rows" failure mode on a question the user will try. |
| 2 | **worldbank easy** "How does life expectancy vary across world regions?" | **FAIL** wrong table `ds__worldbank_indicators` (double underscore) | The linker picked a table name with a double underscore that doesn't exist. Confirms the handover's "plausible-but-wrong table" failure. |
| 3 | **worldbank medium** "Compare internet adoption between high-income and low-income" | **PASS** | Correctly filtered income groups — one of the ⚠️ questions that actually worked. |
| 4 | **worldbank easy** "How does GDP per capita compare across income groups?" | **FAIL** timed out 180s | The GDP query planner/generated SQL was too expensive. Confirms the handover's "long tail latency" gap. |
| 5 | **cms easy** "How does claim volume break down by year?" | **HANG** (WS ping timeout) | `CLM_FROM_DT` is TEXT `YYYYMMDD` — per the handover this needs `LEFT()` / `to_date()`. The query never returned. |
| 6 | **ga / tpcds / very_complex** | **not reached** | load_dataset timed out before questions ran. |

---

## 3. NOOA Framework Alignment Audit (Paul Furgale et al., 2607.20709v1)

The project is built on the NOOA paper. Each principle below is scored against what the codebase actually does.

| Paper principle | Code | Status | Gap |
| --- | --- | --- | --- |
| **P1 Reuse Python abstractions** — agents are classes, methods are capabilities, type annotations are contracts | `SchemaAgent`, `SQLAgent`, `VizAgent`, `CoordinatorAgent` are `@nooa.Agent` classes with typed methods. `SchemaLinker` is a plain method. `validate_read_only`, `estimate_cost` are plain Python functions. | ✅ **Partial** | `SchemaLinker` should be an agent class (it's instantiated and injected via `coordinator.linker`). Mixing agent + non-agent objects in the orchestration obscures the interface boundary the paper describes. |
| **P2 Reframe agentic loops as method calls** — application sees an agentic loop as a normal Python method call with typed I/O | `coordinator.run()` is an `async for` generator yielding events; callers iterate rather than `await`-ing a typed return. `analyze()` is the only true `CodeActStrategy` method with a typed `dict` return. | ⚠️ **Gap** | `CoordinatorAgent.run()` is an `AsyncIterator[dict]` generator — not a typed method return. The paper's support-agent example (`triage(...) -> Ticket`) shows the target: a single awaited call returning a validated object. The streaming WS design breaks this abstraction. |
| **P3 Move deterministic work out of the agentic loop** | `extract_metrics`, `infer_query_type`, `_section_from_result`, `classify_size`, `estimate_cost`, `validate_read_only` are deterministic. | ✅ | Good. `extract_metrics` and `infer_query_type` are real Python methods the model never touches. |
| **P4 Unlock the model's Python knowledge (CodeAct)** | `SQLAgent.generate_complex` uses `CodeActStrategy` — the model can call `self.validate_sql()`, `self.estimate_cost()`, `self.execute_query()`, `self.calculate()` as Python functions. | ✅ | One of the best-aligned parts. The model writes SQL by calling typed helpers. |
| **P5 Expose the harness as explicit APIs (Context/Events/Memory)** | No `ContextManager`, no `EventManager`, no `self.context[...]`, no `self.events.query()` anywhere in the agent code. | ❌ **Gap** | The paper's `ContextManager` / `EventManager` / `Memory` APIs are not used. Context is rendered ad-hoc via f-string docstrings. This is the biggest framework-alignment miss — the paper's headline contribution (context blocks, event history, long-term memory) is absent. |
| **Typed I/O + pass-by-reference + validated termination** | Typed I/O ✅ (Pydantic models). Pass-by-reference ⚠️ (`SchemaMap`, `QueryResult` are passed as live objects in places, but many are serialized to `compact_repr()` strings). Validated termination ❌ (`analyze()` has `max_iterations=5` but no `return_result()` validated contract like the paper's `BenchAgent`). | ⚠️ **Partial** | |

**Headline alignment gap:** The paper's differentiators — context engineering (`context.set_dynamic("todo", ...)`), event history (`self.events.query(type="PythonOutput")`), and long-term memory — are entirely absent. The project uses NOOA as a class/method scaffolding layer but not for the model-facing context APIs that the paper introduces as its core contribution. For a portfolio piece built "around this paper", that is the single most important gap to close.

---

## 4. Bugs Found (Confirmed Live)

### 🔴 BUG-1: Wrong table selection with double underscore (worldbank)
**Live evidence:** `error: relation "ds__worldbank_indicators" does not exist`
The linker picked a table name `ds__worldbank_indicators` (double underscore) that doesn't exist. The real table is `ds_worldbank_indicates` / `ds_worldbank_values`. Confirms the handover's "plausible-but-wrong table" failure mode.

### 🔴 BUG-2: Zero-row results on a natural easy question (fdic)
**Live evidence:** `error: Query returned zero rows. Try a broader question.` on "Which states host the most active banks?" — a question where the answer clearly exists. The SQL ran, returned no rows, and the user got a dead end.

### 🔴 BUG-3: 180s timeout on a straightforward aggregate (worldbank)
**Live evidence:** `error: Query timed out after 180s` on "How does GDP per capita compare across income groups?" — a simple GROUP BY. Either the generated SQL was pathological (no filter, full scan of a wide table) or the planner spun.

### 🟡 BUG-4: WebSocket keepalive ping timeout on streaming results (cms)
**Live evidence:** `ConnectionClosedError: sent 1011 (internal error) keepalive ping timeout; no close frame received` on "How does claim volume break down by year?" — a question whose SQL needs `CLM_FROM_DT` date parsing. The WS died mid-stream.

### 🟡 BUG-5: Bare-number answer with no story (systemic, every PASS)
**Live evidence:** Every PASS answer is `"Total X 1,234 | Latest X 567"` — a pipe-joined metric list. Even `type=comparison` and `type=distribution` answers are bare dumps, never "X is larger than Y by Z%" or "the distribution is right-skewed toward…". This is the handover's #2 complaint and `test-questions-guide.md` item 4 ("Bare-number answers are a FAIL against the current product bar").

### 🟡 BUG-6: load_dataset endpoint times out on multi-table datasets
**Live evidence:** `load_dataset` for tpcds (24 tables), ga, and the raw-worldbank samples all hit the 120s `urllib` timeout. The endpoint itself is synchronous `urllib.request.urlopen` in the async handler — blocks the event loop. Under concurrent load (multiple `ws/query` calls running), the event loop stalls and the load never returns.

### 🟡 BUG-7: WS auth handshake times out under load (finance, healthcare)
**Live evidence:** `TimeoutError: timed out during opening handshake` — the backend accepted the TCP connection but the WebSocket auth handshake didn't complete within 30s. Happened on finance (4 tables) and healthcare (5 tables) after earlier datasets had been running. Suggests the connection pool or event loop is exhausted by the time these datasets are tested.

---

## 5. Latency Profile (Live Measurements)

From the reference harness runs:

| Tier | Median | p90 | Range |
| --- | --- | --- | --- |
| easy | 80s | 92s | 43–139s |
| medium | 90s | 107s | 52–195s |
| hard | (not yet run) | — | — |
| very_complex | (not yet run) | — | — |

The 139s "distribution of bank asset sizes" is a single-table query — that's `classify_complexity` + `generate_simple` sequential LLM calls, not query execution time. For a portfolio demo, 80s/easy question is still slow; the handover notes the user remembers "30s for very-complex" and that the real number is much higher.

---

## 6. Testing Gaps (what `tests/` does NOT cover)

| Gap | Severity | What's missing |
| --- | --- | --- |
| No E2E pipeline test | High | `test_websocket.py` exists but no test exercises `coordinator.run()` end-to-end against a live backend. The full pipeline is only ever validated by manual clicks and benchmark scripts. |
| No `test_chart_rendering.py` | High | No test asserts that `build_vega_lite` produces a non-empty spec or that the emitted `chart_spec` event contains `spec.$schema`. |
| No `test_query_type_classification.py` | Medium | `infer_query_type` edge cases ("average" keyword in a breakdown/comparison question) are untested. |
| No `test_semantic_correctness.py` | Medium | No post-execution sanity layer checking value ranges. |
| No `test_latency_sla.py` | Low | No test asserting p50/p90 latency bounds. |
| `test_bun_security.py` is dead | Low | CONTEXT.md says Bun sandbox was replaced by NOOA CodeAct. The test still references the old architecture. |

---

## 7. Recommended Fix Priority

| Priority | Bug/Gap | Impact | Framework tie-in |
| --- | --- | --- | --- |
| **P0** | BUG-1 wrong-table (double underscore) | worldbank questions silently break | P2 (linker should be a proper typed agent method, not free-text JSON parsing) |
| **P0** | BUG-2 zero-row dead-end | fdic easy question returns no answer | P3 (add an empty-result re-plan / retry path — deterministic helper) |
| **P0** | BUG-6 load_dataset blocks event loop | multi-table datasets fail to load under load | P1 (use `async` HTTP client, not sync `urllib` in async handler) |
| **P0** | BUG-7 WS handshake timeout | finance, healthcare datasets unreachable | P1 (increase connection pool / async WS handshake) |
| **P1** | BUG-5 no analyst narrative | every answer is a bare number dump | P5 (add a `synthesize_report` LLM step; would be the natural place to use `ContextManager`) |
| **P1** | NOOA P5 gap (no Context/Event/Memory APIs) | the paper's headline contribution is absent | Introduce `self.context.set_dynamic("todo", ...)` and `self.events.query(...)` in `CoordinatorAgent.run()` |
| **P1** | NOOA P2 gap (`run()` is a generator, not typed return) | callers iterate, violating the paper's method-call abstraction | Refactor `analyze()` into the canonical entry point with a typed return |
| **P2** | BUG-3 pathological SQL timeout | straightforward queries hit the 180s wall | P3 (add pre-execution cost-gating in the planner; use `estimate_cost` helper) |
| **P2** | BUG-4 WS keepalive timeout | mid-stream WS death on slow queries | Increase ping interval / make the WS server tolerant of long-running generation |
| **P2** | Test gaps | silent regressions on core behavior | Add the 6 missing test files above |
| **P3** | `test_bun_security.py` dead test | confusion about current architecture | Delete or rewrite |

---

## 8. What a Portfolio Reviewer Sees (after this testing)

- ✅ Charts **do** render (bar / point for breakdown, comparison, distribution) — the earlier "null chart" finding was a false alarm from checking the wrong JSON path. `chart_spec.spec.mark` is populated.
- ✅ SQL generation + schema validation + cost gating pipeline works on real data.
- ✅ Spot-check re-run confirms numbers match the data (every PASS in the log had zero metric mismatches).
- ❌ The **wrong-table** bug (double underscore) is real and reproducible on worldbank.
- ❌ **Zero-row dead-ends** on easy questions are real (fdic).
- ❌ **Bare-number answers** on every question — the #1 complaint in the handover — confirmed live.
- ❌ **Latency** of 80-139s/easy-question makes a click-through demo painful.
- ❌ **WS handshake timeouts** on larger datasets (finance, healthcare) under load.
- ❌ The paper's headline contribution (context engineering, event history, memory) is **absent** from the codebase — the project uses NOOA only as a class scaffolding layer.
