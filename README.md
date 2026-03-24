# nl2sql-viz

Ask natural language questions about your database. Get instant Vega-Lite charts.

## Stack

- **Backend:** Python/FastAPI + Claude Agent SDK (Anthropic)
- **Visualization:** Vega-Lite v5 rendered via vega-embed
- **Frontend:** Next.js + Tailwind CSS
- **Database:** PostgreSQL (asyncpg), plugin interface for others

## Setup

```bash
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY and SECRET_KEY

uv sync
docker compose up -d   # starts dev Postgres
uv run uvicorn app.main:app --reload --port 8000
```

## Run tests

```bash
uv run pytest tests/unit/ -v                  # unit tests (no API key needed)
uv run pytest tests/integration/ -v           # integration tests (needs Postgres + API key)
```
