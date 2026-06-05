# SmartOps Local Development Guide

> Related docs: [Deployment](./deployment.md) · [Tech Stack](./tech-stack.md) · [Architecture](./architecture.md) · [Auth & Sessions](./auth-sessions.md) · [Local Database Migrations](./local-database-migrations.md) · [Testing Strategy](./testing-strategy.md)

## Overview

This guide covers full-stack local development: PostgreSQL + FastAPI backend and Flutter mobile app connected to a local or staging API. For production/staging deployment, see [Deployment](./deployment.md).

**Prerequisites:**

| Tool | Version |
|---|---|
| Docker Desktop | Latest |
| Python | 3.12+ |
| Flutter | 3.24+ |
| Dart | 3.5+ |
| Android Studio or Xcode | For emulators |
| Google Cloud project | OAuth credentials for Sign-In |

---

## 1. Clone and Repository Layout

```bash
git clone <repo-url> SmartOps
cd SmartOps
```

When implementation is scaffolded, the repo will contain:

```
SmartOps/
├── mobile/          # Flutter app
├── backend/         # FastAPI app
├── docker-compose.yml
└── docs/
```

---

## 2. Local PostgreSQL (Backend)

Start PostgreSQL via Docker Compose (defined in [Deployment](./deployment.md)):

```bash
docker compose up -d postgres
```

**Connection string:**

```
postgresql+asyncpg://smartops:smartops@localhost:5432/smartops
```

### Backend setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

export DATABASE_URL=postgresql+asyncpg://smartops:smartops@localhost:5432/smartops
export JWT_SECRET=dev-secret-change-in-production
export GOOGLE_CLIENT_ID=<your-google-web-client-id>
export MIN_SUPPORTED_APP_VERSION=1.0.0
export LATEST_APP_VERSION=1.0.0

alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Verify:**

```bash
curl http://localhost:8000/health
# Expected: {"status":"ok"}
```

**OpenAPI (when implemented):** `http://localhost:8000/api/v1/openapi.json`

---

## 3. Google Sign-In (Development)

Google Sign-In requires OAuth credentials for each platform. See [Deployment — Google Sign-In Setup](./deployment.md#google-sign-in-setup).

### Android (primary MVP target)

1. Create OAuth **Android** client in Google Cloud Console
2. Package name: `com.smartops.app` (or your dev package, e.g. `com.smartops.app.dev`)
3. Add SHA-1 fingerprint from debug keystore:

```bash
keytool -list -v -keystore ~/.android/debug.keystore -alias androiddebugkey -storepass android -keypass android
```

4. Add the Android client ID to Flutter config (when implemented):

```dart
// mobile/lib/core/config/env.dart — conceptual
static const googleClientId = String.fromEnvironment('GOOGLE_CLIENT_ID');
```

5. Backend verifies tokens using `GOOGLE_CLIENT_ID` (Web client ID or allowed audience list)

### iOS (when added)

Create OAuth **iOS** client with bundle ID. Add `GoogleService-Info.plist` to Xcode project.

### Local backend token verification

Backend `POST /api/v1/auth/google` accepts Google ID token from mobile. For local dev, mobile must reach backend at a reachable URL:

| Emulator | Backend URL |
|---|---|
| Android emulator | `http://10.0.2.2:8000` |
| iOS simulator | `http://localhost:8000` |
| Physical device | `http://<your-lan-ip>:8000` |

---

## 4. Flutter Mobile Setup

### Install dependencies

```bash
cd mobile
flutter pub get
```

### Flavors and environment config

Use Flutter flavors to switch API URLs between local, staging, and production:

| Flavor | API base URL | Use case |
|---|---|---|
| `dev` | `http://10.0.2.2:8000` (Android) / `http://localhost:8000` (iOS) | Local backend |
| `staging` | `https://api-staging.smartops.app` | QA / beta |
| `production` | `https://api.smartops.app` | Production |

**Run with flavor (when configured):**

```bash
# Android emulator + local backend
flutter run --flavor dev \
  --dart-define=API_BASE_URL=http://10.0.2.2:8000 \
  --dart-define=GOOGLE_CLIENT_ID=<android-client-id> \
  --dart-define=APP_ENV=dev

# Staging
flutter run --flavor staging \
  --dart-define=API_BASE_URL=https://api-staging.smartops.app \
  --dart-define=GOOGLE_CLIENT_ID=<android-client-id> \
  --dart-define=APP_ENV=staging
```

**Required dart-defines (MVP):**

| Define | Example | Purpose |
|---|---|---|
| `API_BASE_URL` | `http://10.0.2.2:8000` | Backend base URL |
| `GOOGLE_CLIENT_ID` | OAuth client ID | Google Sign-In |
| `APP_ENV` | `dev` / `staging` / `production` | Sentry environment tag |
| `SENTRY_DSN` | (optional in dev) | Error tracking |

### Client version headers

Mobile must send on every API request (see [API Versioning](./api-versioning.md)):

```
Authorization: Bearer <access_token>
X-App-Version: 1.0.0
X-Client-Schema-Version: 1
X-Platform: android
X-Device-Id: <uuid>
X-Organization-Id: <uuid>
```

---

## 5. Isar Local Database

SmartOps stores all business data locally in Isar. See [Local Database Migrations](./local-database-migrations.md) for schema versioning.

### Code generation workflow

When Isar collection models change:

```bash
cd mobile
dart run build_runner build --delete-conflicting-outputs
```

**Watch mode during development:**

```bash
dart run build_runner watch --delete-conflicting-outputs
```

### Schema version

- Client schema version is sent as `X-Client-Schema-Version` header
- Increment when Isar collections change; coordinate with server deploy
- Migration runner executes on app startup before sync resumes

### Reset local database (dev only)

```bash
# Uninstall app from emulator, or clear app data in Settings
# Or use a dev-only "Reset local DB" action in debug builds
```

Never ship reset-to-production without backup warning.

---

## 6. Running Mobile Against Local Backend

```mermaid
flowchart LR
  subgraph devMachine [Developer Machine]
    Docker[PostgreSQL :5432]
    FastAPI[FastAPI :8000]
    Flutter[Flutter emulator]
  end
  Flutter -->|10.0.2.2:8000| FastAPI
  FastAPI --> Docker
  Flutter -->|Isar local| IsarDB[(Isar DB)]
  Flutter -->|Google OAuth| Google[Google Sign-In]
  Flutter -->|POST /auth/google| FastAPI
```

**End-to-end local flow:**

1. Start PostgreSQL: `docker compose up -d postgres`
2. Start backend: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
3. Run Flutter with `dev` flavor pointing to emulator-accessible URL
4. Sign in with Google (requires internet for OAuth)
5. Complete onboarding; verify data writes to Isar
6. Trigger sync; verify records appear in PostgreSQL

**Offline testing:** Enable airplane mode after sign-in. Add expense locally. Disable airplane mode. Pull-to-sync or wait for auto-sync. Verify backend received push.

---

## 7. Cloudflare R2 (Optional for Local Dev)

File uploads (expense invoices, employee documents) use presigned R2 URLs. For local dev:

| Option | Detail |
|---|---|
| Use staging R2 bucket | Simplest — point dev flavor at staging presign endpoint |
| Local mock | Backend returns mock presign URLs; skip actual upload in unit tests |
| MinIO | Self-hosted S3-compatible store (advanced) |

See [Deployment — Cloudflare R2 Setup](./deployment.md#cloudflare-r2-setup).

---

## 8. Environment Files

**Backend `.env` (gitignored):**

```env
DATABASE_URL=postgresql+asyncpg://smartops:smartops@localhost:5432/smartops
JWT_SECRET=dev-secret
GOOGLE_CLIENT_ID=<web-client-id>
MIN_SUPPORTED_APP_VERSION=1.0.0
LATEST_APP_VERSION=1.0.0
MIN_SUPPORTED_SCHEMA_VERSION=1
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=smartops-dev
SENTRY_DSN=
```

Do not commit `.env` files. Use `.env.example` in repo with placeholder values.

---

## 9. Common Issues

| Problem | Solution |
|---|---|
| Android emulator cannot reach `localhost:8000` | Use `10.0.2.2:8000` instead |
| Google Sign-In fails on emulator | Verify SHA-1 matches debug keystore; check package name |
| Isar build_runner conflicts | Run with `--delete-conflicting-outputs` |
| Sync push rejected (schema) | Align `X-Client-Schema-Version` with server `MIN_SUPPORTED_SCHEMA_VERSION` |
| 426 Upgrade Required | Set `MIN_SUPPORTED_APP_VERSION` to match app version in dev, or bump app version |

---

## Related Documents

- [Deployment](./deployment.md) — staging/production hosting, CI/CD
- [Testing Strategy](./testing-strategy.md) — offline/sync test scenarios
- [Auth & Sessions](./auth-sessions.md) — token lifecycle
- [Sync Protocol](./sync-protocol.md) — push/pull payload reference
