# Deploy on a $5 VPS (Hetzner CX22) — always-on, no downtime
# Frontend stays on GitHub Pages → backend on the VPS → HTTPS via DuckDNS + Caddy

## Architecture
```
GitHub Pages (static frontend) ──wss://──> https://nl2sql2viz.duckdns.org
                                             │ Caddy (auto-TLS + WS proxy)
                                             ▼ app:8000 (FastAPI)
                                             ▼ postgres:5432 (all datasets)
```

## Step 1 — VPS (Hetzner CX22, $4.70/mo)
1. https://hetzner.com/cloud → account → **Create Server**
   - Location: any (e.g. Ashburn/Falkenstein)
   - Image: **Ubuntu 24.04** · Type: **CX22** (2 vCPU / 4GB RAM / 40GB)
   - Add your SSH key (or use password), create.
2. Note the server IP.

## Step 2 — Free stable subdomain (DuckDNS)
1. https://duckdns.org → sign in (any OAuth) → add a subdomain, e.g. `nl2sql`
2. Set its A record to your server IP:
   `https://duckdns.org/update?domains=nl2sql&token=<your-token>&ip=<server-ip>`
   (the DuckDNS page shows your token; also install their cron client on the
   VPS to keep the IP current: `echo "*/5 * * * * curl -s 'https://duckdns.org/update?domains=nl2sql&token=<token>'" | crontab -`)

## Step 3 — Deploy the stack (one command)
On the VPS (as root):
```bash
apt-get update && apt-get install -y git
git clone https://github.com/Ven-Z8/nl2sql-viz.git /opt/nl2sql-viz
cd /opt/nl2sql-viz/deploy
export POSTGRES_PASSWORD="$(openssl rand -hex 16)"
export OPENROUTER_API_KEY="sk-or-..."
export SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
bash setup.sh
```
- Edit `deploy/Caddyfile` first if your DuckDNS subdomain differs from
  `nl2sql2viz.duckdns.org` (only change needed).
- setup.sh installs Docker, builds, starts Postgres + app + Caddy, and seeds
  all 12 datasets + samples (~10 min).

## Step 4 — Point the frontend at it
1. GitHub repo → Settings → Pages → Source: **GitHub Actions**
2. Settings → Secrets and variables → Actions → Variables:
   - `NEXT_PUBLIC_API_URL` = `https://nl2sql2viz.duckdns.org`
   - `NEXT_PUBLIC_WS_URL` = `wss://nl2sql2viz.duckdns.org/ws/query`
   - `NEXT_PUBLIC_BASE_PATH` = `/nl2sql-viz`
3. Re-run the Pages workflow → live at `https://ven-z8.github.io/nl2sql-viz/`

## Ops
```bash
docker compose -f deploy/docker-compose.prod.yml ps        # status
docker compose -f deploy/docker-compose.prod.yml logs -f app
docker compose -f deploy/docker-compose.prod.yml exec app python scripts/seed_deploy.py  # re-seed
```

## Costs
- Hetzner CX22: **$4.70/mo** (or use Oracle Always Free for $0 — same stack, harder signup)
- DuckDNS: $0 · Caddy TLS: $0 · GitHub Pages: $0 · Domain: **$0**
