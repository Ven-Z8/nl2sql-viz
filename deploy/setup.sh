#!/usr/bin/env bash
# One-time setup for the NL2SQL Viz production stack on a fresh Ubuntu VPS.
# Run as root (or with sudo). Then:
#   export POSTGRES_PASSWORD="$(openssl rand -hex 16)"
#   export OPENROUTER_API_KEY="sk-or-..."
#   export SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
#   bash setup.sh
set -euo pipefail

cd "$(dirname "$0")"

# 1. Docker + compose plugin
if ! command -v docker >/dev/null 2>&1; then
  apt-get update
  apt-get install -y ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

# 2. Required env vars
: "${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD}"
: "${OPENROUTER_API_KEY:?set OPENROUTER_API_KEY}"
: "${SECRET_KEY:?set SECRET_KEY}"
cat > .env <<EOF
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
SECRET_KEY=${SECRET_KEY}
EOF

# 3. Build + start
docker compose -f docker-compose.prod.yml up -d --build

# 4. Seed the data (all datasets + samples). Idempotent — safe to re-run.
echo "Seeding data (this takes ~10 min)…"
docker compose -f docker-compose.prod.yml exec -T app python scripts/seed_deploy.py

echo "Done. HTTPS app at the domain in deploy/Caddyfile"
echo "Check: docker compose -f docker-compose.prod.yml ps"
