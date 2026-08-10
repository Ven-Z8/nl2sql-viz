# NL2SQL Enterprise Research — What We Can Borrow

> Deep research on how enterprises build production NL2SQL / data copilot systems,
> and what a portfolio project can borrow. Sources: BIRD benchmark findings,
> Oracle OCI NL2SQL, semantic-layer vendors (dbt, Cube, AtScale), production
> engineering blogs.

---

## 1. The enterprise reality

Enterprise NL2SQL is much harder than academic benchmarks:
- Schemas have **hundreds of physical tables** with cryptic column names
- Questions need **nested aggregations, time-windowed logic, multi-table joins**
- Heterogeneous SQL dialects
- **Latency vs accuracy** trade-offs at scale

**The core enterprise pattern: decouple schema grounding from SQL synthesis.**
A semantic layer gives the LLM a clean business-level vocabulary (metrics,
dimensions, definitions) instead of raw physical tables. One paper reports
**94.15% accuracy** on enterprise benchmarks with this pattern.

## 2. What the BIRD benchmark teaches

BIRD is the leading text-to-SQL benchmark (real databases, execution accuracy).

| Finding | Number | Implication |
| --- | --- | --- |
| **Domain knowledge is huge** | GPT-4: 54.89% with domain hints vs **34.88% without** (~20pt gap) | Domain skills are the biggest accuracy lever |
| **Execution accuracy matters** | Tests whether SQL *runs correctly*, not string match | Evaluate on executable results, not SQL text |
| **Schema linking is central** | Top systems (Gemini-SQL2, RSL-SQL) focus on it | Select relevant tables/columns before generation |
| **Self-correction verification** | Gemini-SQL2 (80.04% on BIRD) uses it | Validate + retry with feedback |
| **State of the art** | Gemini-SQL2: 80.04% · NeurIPS 2024: 71.83% | The bar for "good" NL2SQL |

## 3. The semantic layer pattern (the big borrow)

Enterprise data copilots (dbt Semantic Layer, Cube, AtScale, LookML) define
**governed metrics, dimensions, and business definitions** in one place, then
compile natural language → metric/dimension requests → SQL.

```
User question → semantic layer (metrics/dimensions) → SQL → warehouse
```

**Why it works:** the LLM maps to a clean business vocabulary instead of
guessing physical column names. This is exactly the "no guessing" principle.

## 4. What we already have (and how it maps)

| Enterprise pattern | Our implementation | Status |
| --- | --- | --- |
| Domain knowledge injection | **SKILL.md bundles** (8 domains: KPIs, patterns, pitfalls) | ✅ |
| Schema grounding | **Focused schema** (active table, 40 cols) + **sample rows** | ✅ |
| Self-correction verification | **SchemaValidator** (verify columns, retry with feedback) | ✅ |
| Multi-agent separation | Coordinator → Schema/SQL/Viz/Planner agents | ✅ |
| Execution accuracy | Queries execute against real Postgres, grounded answers | ✅ |
| SQL guardrails | SQL Guard (read-only) + read-only transactions | ✅ |
| Deterministic math | MathCalculator (no LLM arithmetic) | ✅ |

## 5. What we can borrow (the improvements)

### A. Mini semantic layer — metric registry (highest value)
Define governed metrics per domain in code, and have the LLM map to them:
```json
{
  "retail": {
    "revenue": "SUM(oi.quantity * oi.unit_price) WHERE o.status='completed'",
    "aov": "revenue / COUNT(DISTINCT o.order_id)",
    "refund_rate": "COUNT(refunded orders) / COUNT(orders)"
  }
}
```
The LLM sees metric definitions instead of raw columns → fewer wrong guesses,
consistent business definitions. This is the #1 enterprise pattern we lack.

### B. Column descriptions / semantic enrichment
Add human-readable descriptions to schema columns (e.g., `region` → "customer
geographic region"). The LLM links better when it knows what columns mean.

### C. Benchmark runner with executable accuracy
Score each question by whether the SQL **executes and returns correct results**
(not string match). This is the BIRD lesson — and it's the portfolio proof.

### D. Few-shot examples per domain
Give the LLM 1-2 worked question→SQL examples per domain (from the easy tier).
BIRD shows few-shot + domain evidence is a major accuracy lever.

### E. Interactive planning (BIRD-INTERACT pattern)
Let the user refine a query in a follow-up turn ("only completed orders",
"by month instead of quarter") — the conversational layer of the copilot.

## 6. Recommended priority for the portfolio

1. **Metric registry (semantic layer)** — the biggest enterprise pattern we lack; makes the "no guessing" story complete
2. **Benchmark runner** — executable accuracy scores across all 5 databases × 12 questions = the proof
3. **Column descriptions** — cheap, improves schema linking
4. **Few-shot examples** — cheap, improves accuracy
5. **Interactive follow-up** — the conversational copilot layer

---

*Sources: BIRD benchmark (execution accuracy, domain-knowledge gap), Gemini-SQL2
(80.04% BIRD), Oracle OCI NL2SQL architecture, semantic-layer vendors (dbt
MetricFlow, Cube, AtScale), production Text2SQL engineering blogs.*