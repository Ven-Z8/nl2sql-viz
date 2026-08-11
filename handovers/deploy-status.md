# Deploy Status & Checklist — GitHub Pages + Render (2026-08-10)

## Done (committed + pushed to `github.com/Ven-Z8/nl2sql-viz`)
- **Backend deploy assets**: `Dockerfile`, `render.yaml` (web + Postgres +
  seed job), `scripts/seed_deploy.py`
- **Frontend deploy assets**: `output: 'export'` + `basePath` from env,
  `.github/workflows/pages.yml` (build → GitHub Pages)
- **Demo data committed** (607MB): all 12 datasets' CSVs + real samples.
  `ga/trips.csv` = 250K rows (46.7MB), `finance_lending.csv` = 130K rows
  (96.5MB) — downsampled to fit GitHub's 100MB/file cap; verified they load.
- All code pushed: `main` is up to date at origin.

## TODO — needs the user's cloud accounts (2 steps)

### Step 1 — Render backend
1. https://render.com → sign up (free)
2. **New → Blueprint** → connect `Ven-Z8/nl2sql-viz` → creates web service +
   free Postgres from `render.yaml`
3. Web service → **Environment** → add secrets:
   - `OPENROUTER_API_KEY`
   - `SECRET_KEY` (32-byte hex: `python -c "import secrets; print(secrets.token_hex(32))"`)
4. Optional seed (pre-loads all data, ~10 min): Render → `nl2sql-viz-seed` job
   → **Manual Run**. Without it, the app loads a dataset on demand on first
   click (waits ~1-2 min).
5. Note URL: `https://<service>.onrender.com`

### Step 2 — GitHub Pages frontend
1. Repo → **Settings → Pages** → Source: **GitHub Actions**
2. Repo → **Settings → Secrets and variables → Actions → Variables**:
   - `NEXT_PUBLIC_API_URL` = `https://<service>.onrender.com`
   - `NEXT_PUBLIC_WS_URL` = `wss://<service>.onrender.com/ws/query`
   - `NEXT_PUBLIC_BASE_PATH` = `/nl2sql-viz`
3. **Actions** tab → re-run the Pages workflow (or push a commit)

**Live URL:** `https://ven-z8.github.io/nl2sql-viz/`

## Caveats to disclose to viewers
- Render free tier sleeps after ~15 min idle → first query after wake ~1 min.
- Free Render Postgres **expires after 30 days**.
- The OpenRouter key on the public backend is spendable by anyone who finds
  the URL — use a free/budget-limited model for the demo key.

## Post-deploy checks (fill in when live)
- [ ] Backend: `curl https://<service>.onrender.com/api/datasets` → 200, 12 datasets
- [ ] Demo session: `POST /api/demo/session` → api_key + dsn
- [ ] One query over WS returns result + key_points
- [ ] Pages: `https://ven-z8.github.io/nl2sql-viz/` loads, connects to backend
- [ ] Load a dataset → tiered questions render → click one → chart + narrative
