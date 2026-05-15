# NL2SQL Viz

Natural-language analytics for Postgres. Ask a business question, get a guarded SQL query, and inspect the result as a Vega-Lite chart.

## Overview

NL2SQL Viz turns a database into an analyst-friendly interface. It inspects schema, generates read-only SQL, executes the query, streams status back to the browser, and renders a chart with the SQL visible for review.

## Demo Dataset

The bundled RavenStack dataset models a SaaS business with customer accounts, subscriptions, feature usage, support tickets, and churn events.

| Table | Rows | Example questions |
| --- | ---: | --- |
| `accounts` | 500 | Which referral sources produce the highest average ARR? |
| `subscriptions` | 5,000 | Show monthly recurring revenue by plan tier over time. |
| `feature_usage` | 25,000 | Which features have high usage and high error counts? |
| `support_tickets` | 2,000 | Show support volume and satisfaction by priority. |
| `churn_events` | 600 | Compare churn reasons by initial plan tier. |

See [docs/ravenstack-demo.md](docs/ravenstack-demo.md) for the full walkthrough.

## How It Works

```text
Browser
  -> WebSocket query
  -> FastAPI coordinator
  -> SchemaAgent introspects Postgres
  -> SQLAgent generates read-only SQL
  -> SQL guard validates SELECT/WITH only
  -> Postgres connector executes query
  -> Chart planner selects visualization intent
  -> VizAgent returns Vega-Lite JSON
  -> Next.js UI renders chart + SQL + event log
```

## Highlights

- Async FastAPI backend with WebSocket progress events
- Anthropic SDK calls isolated inside service classes
- Postgres connector with read-only execution guardrails
- Synthetic but realistic SaaS analytics dataset
- Vega-Lite chart rendering in a Next.js frontend
- Unit and integration tests around SQL generation, demo loading, chart planning, auth, and security

## Quick Start

```bash
cp .env.example .env
# Add ANTHROPIC_API_KEY and SECRET_KEY

uv sync
docker compose up -d
uv run python -m scripts.load_ravenstack
uv run uvicorn app.main:app --reload --port 8000
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## Quality Checks

| Check | Command | Notes |
| --- | --- | --- |
| Backend unit tests | `uv run pytest tests/unit -q` | Does not require API keys |
| Backend lint | `uv run ruff check .` | Python style and import checks |
| Frontend typecheck | `cd frontend && npm run typecheck` | TypeScript compile check |
| Demo loader | `uv run python -m scripts.load_ravenstack` | Requires local Postgres |

Current validation:

| Check | Result |
| --- | --- |
| Unit tests | 55 passed |
| Ruff | Passed |
| Frontend typecheck | Passed |

## Safety Boundaries

- Only `SELECT` and `WITH` statements are allowed through the SQL guard.
- Multiple SQL statements are rejected.
- Mutating keywords such as `INSERT`, `UPDATE`, `DELETE`, `DROP`, and `ALTER` are blocked.
- API keys are hashed with Argon2.
- Stored database credentials use AES-256-GCM encryption.
- `.env`, local databases, private keys, virtualenvs, build output, and editor state are ignored.

## Repository Map

```text
app/
  agents/        # schema, SQL, chart, visualization, and coordinator logic
  connectors/    # Postgres connector and DB abstraction
  core/          # auth, demo session, SQL guard, security, session state
  execution/     # Bun sandbox for optional transform code execution
frontend/
  src/app/       # Next.js app shell
  src/components # query panel, event log, chart panel, SQL viewer
data/ravenstack/ # synthetic SaaS analytics CSVs
docs/            # demo notes
tests/           # unit, integration, and security tests
```

## Next Milestones

- Add a screenshot-driven demo walkthrough.
- Add saved queries and a connection wizard.
- Replace raw DSN browser messages with server-side `connection_id` references.
- Add benchmark cases for SQL validity, chart choice, and guardrail rejection.
