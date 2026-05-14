# RavenStack Demo Dataset

RavenStack is the local demo dataset for nl2sql-viz Phase 1 reliability work.
It is a synthetic SaaS analytics dataset by River @ Rivalytics, distributed
with a permissive MIT-like license for educational and portfolio use.

## Tables

- `accounts` — customer metadata, industry, country, signup source, seats, churn flag
- `subscriptions` — subscription lifecycle, plan tier, MRR/ARR, upgrades, downgrades
- `feature_usage` — daily product usage events by subscription and feature
- `support_tickets` — support volume, priority, response time, satisfaction
- `churn_events` — churn date, reason, refund, reactivation, feedback

## Load Data

```bash
docker compose up -d
uv run python -m scripts.load_ravenstack
```

The loader creates the tables in local Postgres and prints expected row counts:

```text
accounts: 500
subscriptions: 5000
feature_usage: 25000
support_tickets: 2000
churn_events: 600
```

Note: the source CSV contains duplicate `feature_usage.usage_id` values, so the
loader uses `usage_event_id BIGSERIAL PRIMARY KEY` and preserves `usage_id` as
the original source identifier.

## Use In The App

The app can connect to any Postgres database through the normal API key + DSN
flow. For local demos, `/api/demo/session` returns a temporary API key and the
configured demo DSN.

Configure the sample DSN with:

```bash
DEMO_DATABASE_URL=postgresql://testuser:testpass@localhost:5432/testdb
```

The frontend falls back to this demo session only when `NEXT_PUBLIC_API_KEY` or
`NEXT_PUBLIC_DSN` is not set. Query execution still uses the normal WebSocket
pipeline; the demo questions are natural-language suggestions, not SQL
shortcuts.

## BI Demo Questions

- Show monthly recurring revenue by plan tier over time.
- Which industries have the most churn events and longest support resolution time?
- Compare churn reasons by initial plan tier.
- Which features have the highest usage but also the highest error counts?
- Show support ticket volume and satisfaction score by priority.
- Which referral sources produce the highest average ARR?
- Find accounts with high seat counts, high support load, and churn events.
