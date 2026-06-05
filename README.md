# SmartOps

Offline-first mobile business management for Indian small businesses. Manage expenses, revenue, employees, attendance, payroll, inventory, and customer/vendor relationships — with English and Hindi UI support.

**Status:** MVP scaffold — `mobile/` (Flutter) and `backend/` (FastAPI) initialized. See [CONTRIBUTING.md](CONTRIBUTING.md) for branch workflow.

**Repository:** https://github.com/Abhorse/SmartOps

---

## Quick Start

| Goal | Start here |
|---|---|
| Understand MVP scope | [docs/mvp-requirements.md](docs/mvp-requirements.md) |
| Set up local development | [docs/local-development.md](docs/local-development.md) |
| Deploy staging/production | [docs/deployment.md](docs/deployment.md) |
| Run tests (when code exists) | [docs/testing-strategy.md](docs/testing-strategy.md) |

---

## Repository Structure (Planned)

```
SmartOps/
├── mobile/                 # Flutter app (offline-first, Isar, Riverpod)
│   ├── lib/
│   │   ├── core/           # auth, sync, router, theme, l10n
│   │   ├── features/       # auth, expenses, payroll, etc.
│   │   └── shared/         # reusable M3 widgets
│   └── test/
├── backend/                # FastAPI + SQLAlchemy + Alembic
│   ├── app/
│   └── tests/
├── docs/                   # Product and technical documentation
├── docker-compose.yml      # Local PostgreSQL
└── .github/workflows/      # CI/CD
```

---

## Documentation Index

### Product and UX

| Document | Description |
|---|---|
| [mvp-requirements.md](docs/mvp-requirements.md) | Personas, user stories, RBAC, acceptance criteria, release plan |
| [ui-ux-design-system.md](docs/ui-ux-design-system.md) | Material Design 3 theme, components, navigation, accessibility |
| [ui-ux-screens.md](docs/ui-ux-screens.md) | Screen specs, wireframes, states, role-based views |
| [revenue-model.md](docs/revenue-model.md) | Freemium pricing tiers and monetization strategy |

### Architecture and Data

| Document | Description |
|---|---|
| [architecture.md](docs/architecture.md) | System design, sync engine, auth, security, scalability |
| [tech-stack.md](docs/tech-stack.md) | Technology choices, version strategy, phase gates |
| [database-design.md](docs/database-design.md) | PostgreSQL + Isar schema, ERD, indexes |
| [sync-protocol.md](docs/sync-protocol.md) | Sync push/pull payloads per entity type |
| [auth-sessions.md](docs/auth-sessions.md) | Google Sign-In, JWT lifecycle, secure storage |
| [api-versioning.md](docs/api-versioning.md) | API versioning, headers, compatibility matrix |
| [local-database-migrations.md](docs/local-database-migrations.md) | Isar schema migrations, recovery flows |

### Operations and Quality

| Document | Description |
|---|---|
| [local-development.md](docs/local-development.md) | Full-stack local setup: backend, Flutter, Isar, Google OAuth |
| [deployment.md](docs/deployment.md) | Neon + Render/Vercel free-tier hosting, CI/CD |
| [testing-strategy.md](docs/testing-strategy.md) | Unit/integration/E2E scope, offline QA, beta checklist |
| [export-formats.md](docs/export-formats.md) | CSV and payslip PDF column/layout specifications |

### Legacy

| Document | Description |
|---|---|
| [app-details.md](docs/app-details.md) | Early brainstorming — **superseded** by docs above |

### Planning artifacts (visual plans)

| Document | Description |
|---|---|
| [docs/plans/](docs/plans/README.md) | Original Cursor planning docs with diagrams — 6 plans from foundation through gap analysis |

---

## Tech Stack Summary

| Layer | Technology |
|---|---|
| Mobile | Flutter 3.x, Dart 3, Material Design 3 |
| Local DB | Isar |
| State | Riverpod |
| Backend | FastAPI, PostgreSQL 16 (Neon) |
| Auth | Google Sign-In + JWT |
| i18n | English + Hindi (ARB + Noto Sans Devanagari) |
| Hosting (MVP) | Neon + Render — ₹0/month free tier |

See [docs/tech-stack.md](docs/tech-stack.md) for full rationale.

---

## MVP Modules

| Module | Priority |
|---|---|
| Auth and onboarding | P0 |
| Dashboard | P0 |
| Expenses and revenue | P0 |
| Employees, attendance, payroll | P0 |
| Offline sync | P0 |
| Inventory | P1 |
| CRM (customers and vendors) | P1 |
| CSV export, payslip PDF | P1 |

---

## Contributing

Documentation-only repo at this stage. When implementation begins:

1. Read [local-development.md](docs/local-development.md) for environment setup
2. Follow patterns in [architecture.md](docs/architecture.md) and [ui-ux-design-system.md](docs/ui-ux-design-system.md)
3. Run tests per [testing-strategy.md](docs/testing-strategy.md) before opening PRs
