# NOOA Paper Alignment — Assessment & Deliberate Deviations

> Audit basis: Furgale et al., "The NOOA Framework: A High-Level Abstraction
> for Building AI Agents" (arXiv 2607.20709), principles P1–P5. This document
> is the honest record of where this project aligns, where it deliberately
> deviates, and why. A portfolio reviewer should read this before judging the
> framework story.

## Scorecard

| Principle | Status | Evidence |
| --- | --- | --- |
| **P1** Reuse Python abstractions (agents = classes, methods = capabilities, type annotations = contracts) | ✅ Strong | `SchemaAgent`, `SQLAgent`, `VizAgent`, `CoordinatorAgent`, `SchemaLinker`, `KeyPointsAgent` are all `@nooa.Agent` classes with typed methods. Deterministic helpers (`extract_metrics`, `infer_query_type`, `validate_read_only`, `estimate_cost`, `classify_size`) are plain Python functions — the model never touches them. |
| **P2** Reframe agentic loops as method calls with typed I/O | ⚠️ Dual design | `CoordinatorAgent.analyze()` is the paper-shaped entry point: `@strategy(CodeActStrategy(...)) async def analyze(question: str) -> dict` — one awaited call, validated termination. `run()` is an async **generator** that streams progress/sql/result events for the WebSocket UI. The generator exists because the product streams; `analyze()` is the typed method-call face. Both are real and deliberate. |
| **P3** Move deterministic work out of the agentic loop | ✅ Strong | Metric extraction, query-type inference, schema validation (sqlglot), cost gating (EXPLAIN), chart planning, result downsampling — all deterministic, tested, and outside any LLM call. |
| **P4** Unlock the model's Python knowledge (CodeAct) | ✅ Strong | `SQLAgent.generate_complex` is CodeAct — the model writes Python calling `self.validate_sql()`, `self.estimate_cost()`, `self.execute_query()`, `self.calculate()` (deterministic math). |
| **P5** Expose the harness as explicit APIs (Context/Events/Memory) | ⚠️ Partial | The paper's `ContextManager` / `EventManager` / long-term-memory APIs are not used. Context is rendered deterministically (schema repr, sample rows, metrics text) rather than through `self.context[...]`. See the deviation note below. |

## Deliberate deviations (and why)

### 1. `SchemaLinker.link()` and `KeyPointsAgent.synthesize()` are plain methods, not `@strategy(PredictStrategy())`
The paper's PredictStrategy validates output through the provider's
**structured-output (json_schema) response format**. The fast model chosen for
these steps — `inclusionai/ling-3.0-flash` on OpenRouter — **rejects
json_schema** (and its providers disagree on json_object: DeepInfra accepts,
Novita rejects). We hit this wall directly. So the linker and key-point
synthesizer call the LLM and parse+validate the JSON **ourselves** (defensive
parsing, one retry), then construct typed Pydantic models. The typed contract
is preserved; the provider-side enforcement is replaced by client-side
validation. This is the same output contract with a different enforcement
point — not a weakening of P1.

### 2. `run()` streams; `analyze()` is the typed method call
The WebSocket UI needs incremental progress events (schema → linking →
generating → executing → summarizing). That requires a generator. The paper's
method-call shape is preserved in `analyze()` (CodeAct, typed return,
validated termination). If we ever drop streaming, `run()` collapses into
`analyze()`.

### 3. P5 context is rendered deterministically instead of via the paper's Context API
Why: (a) the deterministic context (schema, rows, metrics) is small and
exactly known — there is no ambiguity for `self.context.set_dynamic(...)` to
resolve; (b) the paper's event-history query API is designed for debugging and
long-horizon loops, which this pipeline's short, deterministic chain does not
need. **Where P5 would genuinely pay off is the narrative step**: the
KeyPointsAgent could read the actual `QueryResult` events rather than a
pre-rendered string. That is the planned P5 alignment point — it changes what
the model *sees* without changing what the product shows.

## What a reviewer should take away

- The project uses NOOA's class/strategy machinery where it fits (agents,
  typed I/O, CodeAct, Predict) — not as a logo sticker.
- The deviations are documented engineering tradeoffs (provider constraints,
  streaming UX), not ignorance of the paper.
- The remaining P5 gap is a known, scoped item: make the narrative step
  consume execution events through the framework's context/event surface.
