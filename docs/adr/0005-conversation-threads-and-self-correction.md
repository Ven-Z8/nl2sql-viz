# Conversation threads and self-correction (execute-inspect-refine)

**Date:** 2026-08-25 · **Status:** Accepted

## Context

The pipeline answered every question statelessly. Three failure modes fell out
of that: follow-up questions ("what about 2019?", "only the top 5") lost the
referent of the previous turn; a query that *executed* but produced a junk
result (zero rows, one degenerate row, mostly NULLs) was synthesized into an
answer anyway; and over-budget queries were hard-rejected even when a trivial
rewrite (smaller LIMIT, narrower date window) would have fit.

## Decision

### 1. ThreadStore — in-memory per-user conversation registry (`app/core/threads.py`)

A process-wide singleton keyed by `thread_id`, owned by the user who created
it:

- **Bounds:** max 20 turns per thread (oldest dropped past the cap; the 1-based
  turn counter keeps increasing so client-facing indices stay stable), max 50
  threads per user with strict LRU eviction (monotonic access sequence breaks
  same-tick ties), 30-minute idle TTL swept lazily whenever that user touches
  the store.
- **Ownership:** enforced at lookup only — another user's `thread_id` is
  indistinguishable from an unknown one and silently starts a fresh thread.
  It can never raise or leak state.
- **Turn payload:** question text (≤200 chars), executed SQL (≤500 chars),
  row count, a compact summary (≤8 columns × ≤3 example values each — never
  full rows), and the tables the SQL touched (sqlglot parse with a FROM/JOIN
  regex fallback). Braces are neutralized because summaries are interpolated
  into LLM prompt templates.
- **Concurrency:** every operation is synchronous dict/dataclass mutation, so
  under the asyncio event loop each is atomic without locks.
- **Lifecycle:** process restart forgets all threads; clients simply get new
  ids. No persistence — acceptable for V1; horizontal scaling would need an
  external store (out of scope).

### 2. Context injection

The last 10 turns are rendered into a single `CONVERSATION CONTEXT` block and
injected into the SQL-generation prompt. The block is empty when there are no
prior turns, so self-contained questions produce byte-identical prompts to
the old stateless pipeline — threads add zero prompt noise when unused.

### 3. Self-correction budget — 4 executions per user query

One hard cap (`_MAX_EXECUTIONS_PER_QUERY = 4`) covers *all* execution paths
for a single question: clarify round-trips, broaden retries after zero rows,
and refine iterations. The refine loop itself runs at most 2 iterations and
is the only stage that could spiral, so it enforces the ceiling. Inspection
signals (before synthesis): zero rows surviving the retry ladder, a
degenerate single-row aggregate on a breakdown-shaped question, null-dominant
columns (>80% NULL), uniform values (<3 result rows treated as noise). When
inspection flags issues, the report is appended to the regeneration prompt;
a refined query rejected by the cost gate falls back to the last good result
rather than failing the question.

### 4. Deterministic cost tightening ladder

When EXPLAIN cost exceeds `MAX_COST`, up to two automatic rewrites run before
any error is surfaced — no extra LLM calls:

1. **Attempt 1 — LIMIT cap:** add a LIMIT proportional to the budget
   (`max(200, budget // 100)`); halve an existing LIMIT instead.
2. **Attempt 2 — narrow scope:** advance each ISO-date `BETWEEN` window start
   to its midpoint (recent half kept); when no date windows exist, drop a
   JOIN the planner explicitly marked `/* optional_join */` — only if its
   alias is unreferenced afterward.

Tightenings stack across attempts. Still over budget → actionable error with
the estimate vs the ceiling.

### 5. Grouped-answer grounding rule

Grouped-shaped results (explicit GROUP BY, or multiple rows whose first
column is categorical) enumerate their **top ≤5 segments** in the answer
instead of KPI-style labels. Every cited number carries a
`{query_index, row_index}` provenance trace into the shipped result set, and
section metrics without a matching trace are dropped from provenance rather
than shown ungrounded — the same rule that filters narrative key points.

## Consequences

- Follow-ups work conversationally at zero infrastructure cost, but restarts
  forget threads (clients get new ids) and multi-worker deployments would need
  shared storage — documented V1 limits.
- Refine adds latency only when inspection actually flags issues; healthy
  results ship immediately.
- Tightening changes query semantics slightly (fewer rows / narrower window /
  fewer joins) — accepted as strictly better than rejecting usable queries,
  and always announced via a progress event.
- The 4-execution cap bounds worst-case LLM spend per question regardless of
  how many correction stages trigger.
