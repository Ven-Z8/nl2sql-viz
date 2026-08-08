# Deploy to Vercel (frontend) + Railway (backend + Postgres)

The Next.js frontend deploys on Vercel's free tier for instant deploys and excellent DX. The FastAPI backend and managed Postgres run on Railway for simple, affordable hosting with adequate resources for the 1M–5M row target.

**Considered Options:**
- **Vercel + Railway** (chosen) — best DX for Next.js frontend, simple backend hosting
- **Railway only** — single platform but Vercel's Next.js support is superior
- **Fly.io** — better global performance but more configuration
- **Self-hosted VPS** — cheapest at scale but operational overhead

**Why this split:** Vercel's free tier handles the Next.js frontend perfectly with zero config. Railway provides managed Postgres and a Python runtime for FastAPI without the complexity of container orchestration. The resume link needs to just work — this is the fastest path from localhost to a public URL.
