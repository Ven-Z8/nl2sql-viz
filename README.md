# NL2SQL Viz (DataLens AI)

Natural-language analytics for Postgres. Ask a business question, get a guarded
SQL query, and a **grounded answer** (every number from real data — no
hallucination) with an analyst narrative and a chart.

**Live demo:** frontend on GitHub Pages · backend on Render (free tier)

## Architecture

```
Frontend (Next.js 16, static on GitHub Pages)
  │  WebSocket (wss://)
  ▼
FastAPI backend (Render, free tier)
  │  coordinator pipeline:
  │    schema introspection → fast-model schema linking → complexity routing
  │    → SQL generation (DeepSeek flash) → schema validation (no guessing)
  │    → EXPLAIN cost gate → read-only execution → grounded answer
  │    → key-points narrative (grounded) → chart spec
  ▼
PostgreSQL (Render free tier) — 12 relational datasets + 11 CSV samples
```

Every answer number traces to executed query results. The narrative is
synthesized **only** from those numbers.

## Run locally

```bash
docker compose up -d                # Postgres
uv run uvicorn app.main:app --port 8000   # backend
cd frontend && npm run dev          # frontend at :3000
uv run pytest tests -q              # 125 tests
```

`.env` needs: `OPENROUTER_API_KEY`, `SECRET_KEY` (32-byte hex), `DATABASE_URL`.

Load the demo data:

```bash
uv run python -m scripts.load_dataset olist   # any dataset id
# or seed everything:
DATABASE_URL=... uv run python -m scripts.seed_deploy
```

## Deploy (GitHub Pages + Render)

### 1. Backend → Render (free)

1. Push this repo to GitHub (it is already at `github.com/Ven-Z8/nl2sql-viz`).
2. Render dashboard → **New → Blueprint** → connect the repo (`render.yaml` is
   included) — this creates the web service **and** a free Postgres.
3. In the web service **Environment** tab, set secrets:
   - `OPENROUTER_API_KEY` (your key)
   - `SECRET_KEY` (`python -c "import secrets; print(secrets.token_hex(32))"`)
   - Models are pre-set: `NL2SQL_MODEL=openrouter/deepseek/deepseek-v4-flash-0731`,
     `NL2SQL_FAST_MODEL=openrouter/inclusionai/ling-3.0-flash`
4. **Seed the data** (one-time, optional — without it the app loads datasets
   on demand when you click them): trigger the `nl2sql-viz-seed` job from the
   Render dashboard (Manual Run). Takes ~10 min for all 12 datasets.
5. Note the service URL, e.g. `https://nl2sql-viz-api.onrender.com`.

> Render free tier: the service sleeps after ~15 min idle (first query after
> wake takes ~1 min). Free Postgres expires after 30 days.

### 2. Frontend → GitHub Pages

1. Repo **Settings → Pages** → Source: **GitHub Actions**.
2. Repo **Settings → Secrets and variables → Actions → Variables**:
   - `NEXT_PUBLIC_API_URL` = `https://<your-render-service>.onrender.com`
   - `NEXT_PUBLIC_WS_URL` = `wss://<your-render-service>.onrender.com/ws/query`
   - `NEXT_PUBLIC_BASE_PATH` = `/nl2sql-viz` (repo name; leave empty for a
     custom domain)
3. Push to `main` — `.github/workflows/pages.yml` builds the static export and
   deploys. The site is at `https://<user>.github.io/nl2sql-viz/`.

## Test harness

`scripts/reference_harness.py` runs a dataset's question ladder over WebSocket
and **spot-checks every answer** by re-running the SQL against Postgres:

```bash
uv run python -m scripts.reference_harness olist 12 3
```

## Datasets

12 relational databases (7 real: Olist, FDIC, GA bike-share, Census ACS,
TPC-DS, CMS Medicare, World Bank; 5 generated) + 11 CSV samples (incl. real
Lending Club 2.2M, Online Retail 542K). Question ladders per dataset:
easy / medium / hard / very_complex — see `data/datasets/*/questions.json`.

## Docs

- `docs/architecture.md` — system diagram
- `docs/benchmark-report.md` — 137/138 (99%) grounded-answer benchmark
- `docs/nooa-alignment.md` — NOOA framework alignment assessment
- `handovers/` — state, gaps, test-questions guide, test report

## License

Demo data licenses: Olist CC-BY-NC-SA-4.0, World Bank CC-BY-4.0, Census CC0,
CMS public domain, TPC-DS TPC EULA. Kaggle samples per their terms.
