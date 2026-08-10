# NL2SQL Viz — System Architecture

```mermaid
flowchart TB
    subgraph UI["Frontend — Next.js 16 (DataLens AI)"]
        QC["Query Composer"]
        AP["Adaptive Panels<br/>KPI strip · Chart · Table · SQL"]
        TABS["Data Source Tabs<br/>CSV · Databases"]
        THEME["Light/Dark Theme"]
    end

    subgraph API["API Layer — FastAPI"]
        REST["REST Endpoints<br/>register · demo · samples · datasets · upload · connections"]
        WS["WebSocket /ws/query<br/>auth → query → progress/sql/result events"]
    end

    subgraph ORCH["Orchestration — CoordinatorAgent (NOOA)"]
        ROUTE["Complexity Routing<br/>classify_complexity (Predict)"]
        LINK["Schema Linking<br/>fast model picks relevant tables/columns"]
        PLAN["Multi-Query Planning<br/>plan_analysis → sub-questions"]
        PARALLEL["Parallel Generation + Execution<br/>asyncio.gather"]
        REPORT["Report Synthesis<br/>sections from grounded results"]
    end

    subgraph AGENTS["Agents (NOOA)"]
        SA["SchemaAgent<br/>introspection + caching"]
        SL["SchemaLinker<br/>link (fast model, json_object)"]
        SQLA["SQLAgent<br/>generate_simple (Predict) · generate_complex (CodeAct)"]
        VA["VizAgent<br/>plan_chart + build_vega_lite"]
        QP["QueryPlanner<br/>decompose (Predict)"]
    end

    subgraph CORE["Core Services"]
        GUARD["SQL Guard<br/>read-only validation"]
        VALIDATOR["SchemaValidator<br/>column verification — no guessing"]
        MATH["MathCalculator<br/>deterministic derived metrics"]
        RESULT["ResultManager<br/>inline/sampled/aggregated"]
        CACHE["QueryCache<br/>LRU + TTL"]
        COST["CostEstimator<br/>EXPLAIN gate"]
    end

    subgraph DATA["Data Layer — Postgres"]
        DEMO["Demo DB<br/>RavenStack"]
        UPLOADS["Uploaded Tables<br/>upload_* (CSV → COPY)"]
        DATASETS["Relational Datasets<br/>ds_* (multi-table + FKs)"]
    end

    subgraph LLM["LLM Layer — OpenRouter via litellm"]
        DEEPSEEK["DeepSeek Flash<br/>SQL generation"]
        LING["Ling Flash<br/>fast classification + schema linking"]
    end

    subgraph SKILLS["Domain Skills (SKILL.md bundles)"]
        SK["retail · healthcare · finance ·<br/>marketing · saas · operations · hr · general"]
    end

    QC --> WS
    TABS --> REST
    AP --> WS
    THEME --> AP

    WS --> ROUTE
    REST --> DATA

    ROUTE -->|simple| SQLA
    ROUTE -->|complex| PLAN
    PLAN --> PARALLEL
    PARALLEL --> SQLA
    SQLA --> VALIDATOR
    VALIDATOR --> GUARD
    GUARD --> DATA
    DATA --> RESULT
    RESULT --> REPORT
    REPORT --> WS

    SA --> DATA
    SL --> SA
    SL --> LING
    SQLA --> SL
    SQLA --> SA
    SQLA --> MATH
    SQLA --> COST
    SQLA --> SKILLS
    QP --> SKILLS
    VA --> RESULT
    VA --> WS

    SQLA --> DEEPSEEK
    QP --> LING
    ROUTE --> LING

    UPLOADS --> DEMO
    DATASETS --> DEMO
```

## Key Flows

### 0. Schema grounding (every query)

```
Schema introspection → scope to active dataset (FK-connected graph of focus table)
→ SchemaLinker (fast model) picks relevant tables/columns → filter_to(linked)
→ SQL model generates against the small, correct context
```

### 1. Simple query (fast path)

```
Question → classify (Predict) → SIMPLE → generate_simple (Predict, ~10s)
→ SchemaValidator (verify columns) → SQL Guard → execute → grounded answer → chart
```

### 2. Very-complex query (multi-query + report)

```
Question → classify → COMPLEX → plan_analysis (sub-questions, ~3s)
→ generate each SQL in parallel → validate each (retry with feedback if wrong)
→ execute all in parallel → synthesize report sections → result
```

### 3. CSV upload

```
File → stream to temp → type inference → COPY into Postgres (upload_* table)
→ schema introspection picks it up → queryable via the same pipeline
```

### 4. Relational dataset load

```
schema.json (tables + FKs) → create tables with constraints → stream each CSV via COPY
→ question ladder (easy/medium/hard/very_complex) shown in UI
```

## Safety & Grounding

- **SQL Guard**: SELECT/WITH only, no mutating keywords, single statement
- **SchemaValidator**: every column verified against the real schema — wrong columns fixed or rejected with feedback (no guessing)
- **MathCalculator**: derived metrics computed deterministically, never by the LLM
- **Read-only transactions**: Postgres `transaction(readonly=True)` at execution
- **Cost gate**: EXPLAIN rejects queries estimated to scan > threshold rows
