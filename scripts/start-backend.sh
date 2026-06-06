#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Starting SmartOps backend on http://0.0.0.0:8000"
cd "$ROOT/backend"

if [ ! -d .venv ]; then
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
else
  source .venv/bin/activate
fi

# shellcheck source=/dev/null
source "$ROOT/scripts/load-backend-env.sh" "$ROOT/backend/.env"

export DEBUG="${DEBUG:-true}"
export AUTH_DEV_MODE="${AUTH_DEV_MODE:-true}"
export DATABASE_URL="${DATABASE_URL:-sqlite+aiosqlite:///./smartops_dev.db}"

echo "    DATABASE_URL=${DATABASE_URL%%@*}@***"
echo "    AUTH_DEV_MODE=$AUTH_DEV_MODE"
echo "    GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID:-(not set)}"

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
