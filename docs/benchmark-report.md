# NL2SQL Viz — Benchmark Report

_Generated nl2sql-viz — 138 questions across 12 datasets_

## Executive Summary

| Metric | Value |
| --- | --- |
| Questions run | 138 |
| Passed (result produced) | 137 (99%) |
| Failed | 1 |
| Avg wall time / question | 2.2m |

> **What "passed" means:** the pipeline produced a grounded result — schema linking → SQL generation → schema validation → execution → answer. A failure means the pipeline errored (wrong table/column that validation couldn't fix, timeout, or zero rows).

## Per-Dataset Results

| Dataset | Domain | Passed | Failed | Pass % | Avg time |
| --- | --- | ---: | ---: | ---: | ---: |
| census | demographics | 11 | 0 | 100% | 1.7m |
| cms | healthcare | 11 | 0 | 100% | 1.5m |
| demographics_census | demographics | 12 | 0 | 100% | 2.3m |
| demographics_consumer | demographics | 12 | 0 | 100% | 2.5m |
| fdic | finance | 10 | 1 | 91% | 1.5m |
| finance | finance | 12 | 0 | 100% | 3.3m |
| ga | marketing | 11 | 0 | 100% | 2.1m |
| healthcare | healthcare | 12 | 0 | 100% | 2.6m |
| olist | retail | 12 | 0 | 100% | 1.2m |
| retail | retail | 12 | 0 | 100% | 3.1m |
| tpcds | operations | 11 | 0 | 100% | 2.0m |
| worldbank | demographics | 11 | 0 | 100% | 2.4m |

## By Difficulty Tier

| Tier | Passed | Failed | Pass % | Avg time |
| --- | ---: | ---: | ---: | ---: |
| easy | 36 | 0 | 100% | 1.0m |
| medium | 36 | 0 | 100% | 1.6m |
| hard | 36 | 0 | 100% | 2.4m |
| very_complex | 29 | 1 | 97% | 4.1m |

## Failure Analysis

1 questions failed. Common causes:

- **All planned queries returned zero rows. ** — 1×

| Dataset | Tier | Question | Error |
| --- | --- | --- | --- |
| fdic | very_complex | Compare 2020 vs 2024 bank profitability: how did ROE and net | All planned queries returned zero rows. Try a broader question. |

## How the System Worked

Every question went through the same grounded pipeline:

1. **Schema introspection** — the active dataset's tables and columns are read from Postgres (FK-connected graph of the focus table).
2. **Schema linking** — a fast model (Ling flash) reads the question + dataset schema and picks the relevant tables/columns, so the SQL model never guesses across the whole database.
3. **Complexity routing** — a classifier decides simple (single query) vs complex (multi-query plan + report).
4. **SQL generation** — DeepSeek flash generates SQL against the small, linked schema.
5. **Schema validation** — every column reference is verified against the real schema; typos and case mismatches are fixed, unresolvable references trigger a retry with feedback (no guessing).
6. **Execution** — read-only, cost-gated queries run against Postgres.
7. **Grounded answer** — every number in the answer comes from executed results; complex questions synthesize a multi-section report.

### What the numbers show

- **137/138 questions (99%)** produced a grounded result across 12 real and generated databases.
- Average wall time per question: **2.2m** (schema linking ~3-8s, generation ~20-60s, execution ~1-5s).
- The 1 failures are dominated by the model picking the wrong table/column that validation could not resolve — the validator catches most mistakes, but a wrong table choice with plausible column names can still slip through.
