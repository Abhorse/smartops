# SmartOps MVP Deployment Guide

> Related docs: [Tech Stack](./tech-stack.md) · [Architecture](./architecture.md) · [Auth & Sessions](./auth-sessions.md) · [API Versioning](./api-versioning.md) · [Local Database Migrations](./local-database-migrations.md) · [Local Development](./local-development.md) · [Testing Strategy](./testing-strategy.md)

## Overview

This guide covers deploying SmartOps MVP on **free-tier infrastructure**. The recommended stack is **Neon (PostgreSQL) + Render (FastAPI)**. **Neon + Vercel** is documented as an alternative with known limitations for sync-heavy workloads.

**MVP recurring infra cost: ₹0/month** (excluding one-time Google Play fee and optional Apple Developer Program).

---

## Architecture Overview

```mermaid
flowchart TB
  subgraph mobile [Mobile]
    FlutterApp[Flutter App]
  end

  subgraph optionA [Option A: Vercel + Neon]
    Vercel[Vercel Hobby - FastAPI]
    NeonA[(Neon PostgreSQL Free)]
  end

  subgraph optionB [Option B: Render + Neon - Recommended]
    Render[Render Free Web Service]
    NeonB[(Neon PostgreSQL Free)]
  end

  subgraph shared [Shared Free Services]
    R2[Cloudflare R2 - file storage]
    Sentry[Sentry - error tracking]
    GHA[GitHub Actions - CI/CD]
    Google[Google OAuth - auth]
  end

  FlutterApp --> Vercel
  FlutterApp --> Render
  Vercel --> NeonA
  Render --> NeonB
  Vercel --> R2
  Render --> R2
  Vercel --> Sentry
  Render --> Sentry
  FlutterApp --> Google
  FlutterApp -->|presigned upload| R2
```

---

## Free Tier Cost Breakdown

| Service | Role | Free allowance | MVP cost |
|---|---|---|---|
| [Neon](https://neon.com) | PostgreSQL | 0.5 GB storage, 100 CU-hours/project/mo, 5 GB egress | ₹0 |
| [Vercel Hobby](https://vercel.com) | FastAPI backend (Option A) | Serverless, 100 GB bandwidth | ₹0 |
| [Render Free](https://render.com) | FastAPI backend (Option B) | 750 instance hours/mo | ₹0 |
| [Cloudflare R2](https://developers.cloudflare.com/r2/) | Invoice photos, documents | 10 GB storage, no egress fees | ₹0 |
| [Sentry](https://sentry.io) | Error tracking | 5,000 errors/mo | ₹0 |
| [GitHub Actions](https://github.com/features/actions) | CI/CD | 2,000 min/mo (private repo) | ₹0 |
| Google Cloud Console | Google Sign-In OAuth | Unlimited auth | ₹0 |
| Google Play Console | Android distribution | One-time $25 (~₹2,100) | One-time |
| Apple Developer Program | iOS / TestFlight | $99/year (~₹8,300/yr) | Optional for beta |

---

## Option Comparison: Vercel vs Render

| Criteria | Vercel + Neon | Render + Neon |
|---|---|---|
| Monthly cost | ₹0 | ₹0 |
| FastAPI fit | Serverless function; official support | Container with Uvicorn |
| Request timeout | **10 s** on Hobby plan | No hard timeout on free tier |
| Cold start | 1–5 s after idle | ~1 min after 15 min idle |
| Sync batch safety | Risk if push/pull exceeds 10 s | Safer for large batches |
| Background workers | Not supported | Not on free tier (OK for MVP) |
| WebSockets | Not supported | Supported (not needed in MVP) |
| Setup complexity | Medium (`vercel.json`, pooler required) | Low (`render.yaml`) |
| **Recommendation** | OK for early beta with small sync batches | **Primary recommendation** |

---

## Environments

| Environment | Backend | Database | Purpose |
|---|---|---|---|
| `development` | Local (`uvicorn` + Docker Postgres) | Local PostgreSQL container | Developer machines |
| `staging` | Render or Vercel (preview) | Neon branch (`staging`) | QA, beta testers |
| `production` | Render or Vercel (main) | Neon main branch | Live users |

### Neon branching strategy

Neon supports database branches (like git branches). Free plan: **10 branches per project**.

| Branch | Use |
|---|---|
| `main` | Production data |
| `staging` | Long-lived staging environment |
| `preview-pr-123` | Ephemeral branch per PR (optional) |

Create staging branch from Neon dashboard → copy connection string → use in staging env vars.

---

## Option A: Vercel + Neon

### Prerequisites

- GitHub repo with SmartOps backend code
- [Neon](https://neon.com) account (free)
- [Vercel](https://vercel.com) account (Hobby/free)
- [Cloudflare](https://cloudflare.com) account for R2

### Step 1: Create Neon database

1. Create project at [console.neon.tech](https://console.neon.tech)
2. Select region closest to users (e.g. `ap-southeast-1` for India)
3. Copy **pooled connection string** (required for serverless):
   ```
   postgresql://user:pass@ep-xxx-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
   ```
4. Note: Neon scales to zero after 5 min idle on free tier — first query may add ~500 ms latency

### Step 2: Configure Vercel project

1. Import GitHub repo in Vercel dashboard
2. Set root directory to `backend/`
3. Add environment variables (see [Environment Variables](#environment-variables))

### Step 3: Vercel configuration

**`backend/vercel.json`:**

```json
{
  "builds": [
    {
      "src": "app/main.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "app/main.py"
    }
  ]
}
```

**`backend/app/main.py`** — FastAPI app instance must be named `app`:

```python
from fastapi import FastAPI

app = FastAPI(title="SmartOps API")

@app.get("/health")
async def health():
    return {"status": "ok"}
```

Or use `pyproject.toml`:

```toml
[tool.vercel]
entrypoint = "app/main.py"
```

### Step 4: Database connection (serverless-safe)

Use Neon's pooled endpoint. Configure SQLAlchemy with short-lived connections:

```python
# Conceptual — use NullPool for serverless
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

engine = create_async_engine(
    settings.database_url,  # pooled Neon URL
    poolclass=NullPool,
)
```

**Never** use a persistent connection pool on Vercel — each invocation is ephemeral.

### Step 5: Run Alembic migrations

Run migrations in CI before deploy (recommended), not inside the serverless function:

```yaml
# .github/workflows/deploy.yml
- name: Run database migrations
  env:
    DATABASE_URL: ${{ secrets.NEON_DATABASE_URL }}
  run: |
    cd backend
    pip install -r requirements.txt
    alembic upgrade head
```

### Vercel limitations and mitigations

| Limitation | Mitigation |
|---|---|
| 10 s timeout (Hobby) | Keep sync batches ≤ 50 records; paginate pull |
| Cold starts | Mobile app shows loading state; retry with backoff |
| No persistent disk | Use R2 for all file storage |
| No Celery | Deferred to Phase 2 anyway |

---

## Option B: Render + Neon (Recommended)

### Prerequisites

Same as Option A except Render account instead of Vercel.

### Step 1: Create Neon database

Same as Option A. Use separate branches for staging and production.

### Step 2: Create Render web service

1. Go to [dashboard.render.com](https://dashboard.render.com) → New → Web Service
2. Connect GitHub repo
3. Configure:

| Setting | Value |
|---|---|
| Root directory | `backend` |
| Runtime | Python 3 |
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Instance type | **Free** |

### Step 3: Render blueprint (optional)

**`render.yaml`** at repo root:

```yaml
services:
  - type: web
    name: smartops-api
    runtime: python
    rootDir: backend
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DATABASE_URL
        sync: false
      - key: JWT_SECRET
        generateValue: true
      - key: GOOGLE_CLIENT_ID
        sync: false
      - key: ENVIRONMENT
        value: production
    healthCheckPath: /health
```

### Step 4: Environment variables

Add all variables from [Environment Variables](#environment-variables) in Render dashboard → Environment.

### Step 5: Database connection

Render supports persistent connections. Use Neon's **pooled** connection string:

```python
engine = create_async_engine(
    settings.database_url,
    pool_size=5,
    max_overflow=10,
)
```

### Step 6: Auto-deploy

Enable auto-deploy on push to `main`. Run Alembic in GitHub Actions before merge (see CI/CD section).

### Render free tier notes

- Spins down after **15 minutes** of no traffic (~1 min to wake up)
- **750 instance hours/month** — sufficient for MVP beta
- Ephemeral filesystem — use R2 for file persistence
- Not suitable for production at scale — upgrade to Starter ($7/mo) when needed

---

## Environment Variables

### Backend (Render or Vercel)

| Variable | Required | Description | Example |
|---|---|---|---|
| `DATABASE_URL` | Yes | Neon pooled connection string | `postgresql+asyncpg://...` |
| `JWT_SECRET` | Yes | Random 256-bit secret for JWT signing | Generate with `openssl rand -hex 32` |
| `JWT_ACCESS_EXPIRE_MINUTES` | No | Access token TTL | `15` |
| `JWT_REFRESH_EXPIRE_DAYS` | No | Refresh token TTL | `30` |
| `GOOGLE_CLIENT_ID` | Yes | Google OAuth client ID (Android + iOS + Web) | From Google Cloud Console |
| `GOOGLE_CLIENT_ID_IOS` | No | iOS-specific client ID if different | |
| `ENVIRONMENT` | Yes | `development` / `staging` / `production` | `production` |
| `CORS_ORIGINS` | No | Allowed origins (mobile uses none) | `*` for MVP |
| `SENTRY_DSN` | No | Backend error tracking | From Sentry project |
| `R2_ACCOUNT_ID` | Yes | Cloudflare account ID | |
| `R2_ACCESS_KEY_ID` | Yes | R2 API token access key | |
| `R2_SECRET_ACCESS_KEY` | Yes | R2 API token secret | |
| `R2_BUCKET_NAME` | Yes | Storage bucket name | `smartops-files` |
| `R2_PUBLIC_URL` | No | Custom domain for public assets | |

**Never commit secrets to git.** Use Render/Vercel environment variable UI or GitHub Secrets.

### Mobile app (build flavors)

| Variable | Description |
|---|---|
| `API_BASE_URL` | Backend URL per flavor |
| `GOOGLE_CLIENT_ID` | Android OAuth client ID |
| `SENTRY_DSN` | Mobile error tracking |

Example flavors:

| Flavor | `API_BASE_URL` |
|---|---|
| dev | `http://10.0.2.2:8000` (Android emulator) |
| staging | `https://smartops-api-staging.onrender.com` |
| prod | `https://smartops-api.onrender.com` |

---

## Cloudflare R2 Setup

1. Create R2 bucket: `smartops-files`
2. Create API token with Object Read & Write permissions
3. Configure CORS for mobile presigned uploads:

```json
[
  {
    "AllowedOrigins": ["*"],
    "AllowedMethods": ["GET", "PUT", "HEAD"],
    "AllowedHeaders": ["*"],
    "MaxAgeSeconds": 3600
  }
]
```

4. Backend generates presigned PUT URLs; mobile uploads directly to R2
5. Store object key in PostgreSQL (not the file itself)

**Free tier:** 10 GB storage, 1 million Class A ops/mo, 10 million Class B ops/mo, **zero egress fees**.

---

## Google Sign-In Setup

1. Create project in [Google Cloud Console](https://console.cloud.google.com)
2. Enable Google Sign-In API
3. Create OAuth 2.0 credentials:
   - **Android:** package name + SHA-1 fingerprint
   - **iOS:** bundle ID (when iOS is added)
   - **Web:** for backend token verification (optional)
4. Add `GOOGLE_CLIENT_ID` to backend env vars
5. Add Android client ID to Flutter app config

**Cost:** Free for authentication.

---

## CI/CD Pipeline

**`.github/workflows/deploy.yml`:**

```yaml
name: Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
          pip install pytest httpx
      - name: Run tests
        run: cd backend && pytest

  migrate-staging:
    needs: test
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Alembic on staging branch
        env:
          DATABASE_URL: ${{ secrets.NEON_STAGING_DATABASE_URL }}
        run: |
          cd backend
          pip install -r requirements.txt
          alembic upgrade head

  migrate-production:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Alembic migrations
        env:
          DATABASE_URL: ${{ secrets.NEON_DATABASE_URL }}
        run: |
          cd backend
          pip install -r requirements.txt
          alembic upgrade head
    # Render/Vercel auto-deploys after this workflow passes
```

### Server migration rules

- Forward-only Alembic migrations (see [Database Design](./database-design.md))
- Run migrations **before** deploying new backend code
- Coordinate with mobile Isar migrations (see [Local Database Migrations](./local-database-migrations.md))

### API version deployment rules

When deploying breaking API changes (see [API Versioning](./api-versioning.md)):

- Deploy `/api/v2` routes **alongside** `/api/v1` — never replace v1 in a single deploy
- Keep v1 active for the full 90-day deprecation window
- Set `MIN_SUPPORTED_APP_VERSION` and sunset date in environment variables before retiring v1
- Run the cross-version testing matrix (old app + new server) before sunset
- Remove v1 routes only after sunset date and confirming zero v1 traffic in logs

---

## Local Development

For full-stack setup including Flutter flavors, Isar code generation, and mobile-backend connectivity, see **[Local Development Guide](./local-development.md)**.

**Quick backend start** (PostgreSQL via Docker):

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: smartops
      POSTGRES_PASSWORD: smartops
      POSTGRES_DB: smartops
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

```bash
# Start local DB
docker compose up -d postgres

# Run backend
cd backend
export DATABASE_URL=postgresql+asyncpg://smartops:smartops@localhost:5432/smartops
alembic upgrade head
uvicorn app.main:app --reload
```

---

## Monitoring

### Sentry

1. Create project at [sentry.io](https://sentry.io) (free tier: 5k errors/mo)
2. Add `SENTRY_DSN` to backend env vars
3. Add DSN to Flutter app via `--dart-define` or flavor config
4. Track: unhandled exceptions, sync failures, migration errors

### Health check

Backend exposes `GET /health`:

```json
{"status": "ok", "database": "connected", "version": "1.0.0"}
```

Render uses this for health checks. Vercel: configure in dashboard or use uptime monitor.

---

## Free Tier Limits and Upgrade Triggers

| Service | Free limit | Upgrade trigger |
|---|---|---|
| Neon storage | 0.5 GB | > 400 MB used consistently |
| Neon compute | 100 CU-hours/mo | DB suspended mid-month |
| Neon egress | 5 GB/mo | Heavy sync traffic |
| Render | 750 instance hours/mo | Service suspended before month end |
| Render | 15 min spin-down | Users complain about 1 min cold start |
| Vercel | 10 s request timeout | Sync batches timing out |
| R2 | 10 GB | Many invoice photos accumulated |
| Sentry | 5k errors/mo | Frequent error spam in beta |

### Recommended upgrade path

| Stage | Backend | Database | Est. cost |
|---|---|---|---|
| MVP beta | Render Free + Neon Free | ₹0/mo |
| Public launch | Render Starter ($7/mo) + Neon Free | ~₹600/mo |
| Growth | Render Standard + Neon Launch | ~₹2,000–5,000/mo |
| Scale | AWS/GCP + Neon Scale | Custom |

---

## Deployment Checklist (Beta Launch)

- [ ] Neon production project created with pooled connection string
- [ ] Neon staging branch created
- [ ] Backend deployed (Render or Vercel) with all env vars set
- [ ] Alembic migrations applied to production
- [ ] `GET /health` returns 200
- [ ] Google Sign-In works end-to-end (mobile → backend → JWT)
- [ ] R2 bucket created with CORS configured
- [ ] Presigned upload flow tested from mobile
- [ ] Sentry receiving test errors from backend and mobile
- [ ] Mobile app `API_BASE_URL` points to production backend
- [ ] SSL/HTTPS verified on all endpoints
- [ ] `MIN_SUPPORTED_APP_VERSION` env var set on staging and production
- [ ] Staging environment tested before production promote

---

## Related Documents

- [Tech Stack](./tech-stack.md) — technology choices
- [Architecture](./architecture.md) — system design
- [Auth & Sessions](./auth-sessions.md) — Google OAuth, JWT setup
- [Local Database Migrations](./local-database-migrations.md) — mobile schema updates
- [API Versioning](./api-versioning.md) — deploy v2 alongside v1; sunset process
- [Database Design](./database-design.md) — PostgreSQL schema, Alembic
- [Revenue Model](./revenue-model.md) — infra cost projections
