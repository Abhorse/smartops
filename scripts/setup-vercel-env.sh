#!/usr/bin/env bash
# Push backend/.env values to Vercel (requires: npm/npx + vercel login or VERCEL_TOKEN).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${1:-$ROOT/backend/.env}"
VERCEL_URL="${VERCEL_URL:-https://ab.smartops1.vercel.app}"

# shellcheck source=/dev/null
source "$ROOT/scripts/load-backend-env.sh" "$ENV_FILE"

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL missing in $ENV_FILE"
  exit 1
fi

if ! command -v npx >/dev/null 2>&1; then
  echo "ERROR: npx not found. Install Node.js first."
  exit 1
fi

cd "$ROOT/backend"

echo "==> Linking Vercel project (backend/)..."
npx --yes vercel link --yes --project ab.smartops1 2>/dev/null || \
  npx --yes vercel link --yes 2>/dev/null || true

set_env() {
  local key="$1"
  local value="$2"
  local target="${3:-production,preview,development}"
  printf '%s' "$value" | npx --yes vercel env add "$key" "$target" --force --yes 2>/dev/null || \
    printf '%s' "$value" | npx --yes vercel env add "$key" "$target" --force
  echo "    set $key"
}

echo "==> Setting Vercel environment variables..."
set_env DATABASE_URL "${DATABASE_URL}"
set_env JWT_SECRET "${JWT_SECRET:-$(openssl rand -hex 32)}"
set_env GOOGLE_CLIENT_ID "${GOOGLE_CLIENT_ID:-}"
set_env AUTH_DEV_MODE "${AUTH_DEV_MODE:-false}"
set_env DEBUG "${DEBUG:-false}"
set_env SKIP_STARTUP_DB_INIT "1"
set_env MIN_SUPPORTED_APP_VERSION "${MIN_SUPPORTED_APP_VERSION:-1.0.0}"
set_env LATEST_APP_VERSION "${LATEST_APP_VERSION:-1.0.0}"
set_env MIN_SUPPORTED_SCHEMA_VERSION "${MIN_SUPPORTED_SCHEMA_VERSION:-1}"

echo "==> Deploying to Vercel..."
npx --yes vercel deploy --prod --yes

echo ""
echo "==> Done. Health check:"
echo "    curl ${VERCEL_URL}/api/v1/health"
