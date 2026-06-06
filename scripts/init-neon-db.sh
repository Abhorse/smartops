#!/usr/bin/env bash
# Create SmartOps tables + seed roles on Neon (run once before or after first Vercel deploy).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"

# shellcheck source=/dev/null
source "$ROOT/scripts/load-backend-env.sh" "$ROOT/backend/.env"

if [ -z "${DATABASE_URL:-}" ] || [[ "$DATABASE_URL" == sqlite* ]]; then
  echo "ERROR: Set DATABASE_URL in backend/.env to your Neon pooled URL first."
  exit 1
fi

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck source=/dev/null
source .venv/bin/activate
pip install -q -r requirements.txt

echo "==> Initializing database schema on Neon..."
python3 - <<'PY'
import asyncio

from app.core.database import init_db


async def main() -> None:
    await init_db()
    print("Database ready (tables + default roles).")


asyncio.run(main())
PY
