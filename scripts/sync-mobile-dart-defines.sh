#!/usr/bin/env bash
# Sync mobile config from backend/.env (runtime asset + optional dart-defines file).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${1:-$ROOT/backend/.env}"
DART_DEFINES_FILE="${2:-$ROOT/mobile/dart_defines.json}"
ASSET_FILE="${3:-$ROOT/mobile/assets/config/env.json}"

# shellcheck source=/dev/null
if [ -f "$ENV_FILE" ]; then
  source "$ROOT/scripts/load-backend-env.sh" "$ENV_FILE"
else
  echo "==> Warning: $ENV_FILE not found — using defaults (run make mobile-config after creating .env)"
fi

API_BASE_URL="${API_BASE_URL:-http://10.0.2.2:8000}"
APP_ENV="${APP_ENV:-dev}"
GOOGLE_CLIENT_ID="${GOOGLE_CLIENT_ID:-}"
AUTH_DEV_MODE="${AUTH_DEV_MODE:-true}"

mkdir -p "$(dirname "$ASSET_FILE")"

python3 - "$DART_DEFINES_FILE" "$ASSET_FILE" "$API_BASE_URL" "$APP_ENV" "$AUTH_DEV_MODE" "$GOOGLE_CLIENT_ID" <<'PY'
import json
import sys
from pathlib import Path

dart_out, asset_out, api, app_env, auth_dev, google_id = sys.argv[1:7]
data = {
    "API_BASE_URL": api,
    "APP_ENV": app_env,
    "AUTH_DEV_MODE": auth_dev.lower(),
}
if google_id:
    data["GOOGLE_CLIENT_ID"] = google_id

payload = json.dumps(data, indent=2) + "\n"
Path(dart_out).write_text(payload, encoding="utf-8")
Path(asset_out).write_text(payload, encoding="utf-8")
print(f"==> Wrote {dart_out}")
print(f"==> Wrote {asset_out}")
PY
