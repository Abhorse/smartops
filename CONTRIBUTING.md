# Contributing to SmartOps

## Repository

- **GitHub:** https://github.com/Abhorse/SmartOps
- **Structure:** Monorepo — `mobile/` (Flutter), `backend/` (FastAPI), `docs/` (planning)

## Branch strategy

| Branch | Purpose |
|---|---|
| `main` | Production-ready releases; protected |
| `develop` | Integration branch for ongoing MVP work |
| `feature/*` | New features — branch from `develop` |
| `fix/*` | Bug fixes — branch from `develop` or `main` for hotfixes |

### Workflow

```bash
git checkout develop
git pull origin develop
git checkout -b feature/expense-module
# ... work, commit ...
git push -u origin feature/expense-module
# Open PR into develop
```

When a release is ready, merge `develop` → `main` via pull request.

## Local setup

See [docs/local-development.md](docs/local-development.md).

## Tests

```bash
# Backend
cd backend && pip install -r requirements.txt && pytest

# Mobile
cd mobile && flutter pub get && flutter test
```

## Commit messages

Use clear, imperative subjects:

- `feat(mobile): add expense list screen`
- `feat(backend): implement sync push endpoint`
- `docs: update sync protocol`
