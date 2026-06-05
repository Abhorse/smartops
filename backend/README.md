# SmartOps Backend

FastAPI backend for SmartOps. See [docs/local-development.md](../docs/local-development.md).

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check: `GET http://localhost:8000/api/v1/health`

## Tests

```bash
pytest
```
