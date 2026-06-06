#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

"$ROOT/scripts/sync-mobile-dart-defines.sh"

# shellcheck source=/dev/null
source "$ROOT/scripts/load-backend-env.sh" "$ROOT/backend/.env"

echo "==> Running SmartOps mobile"
echo "    Config: mobile/dart_defines.json (from backend/.env)"
echo "    API_BASE_URL=${API_BASE_URL:-http://10.0.2.2:8000}"
echo "    AUTH_DEV_MODE=${AUTH_DEV_MODE:-}"
echo "    GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID:-(not set)}"

cd "$ROOT/mobile"
flutter pub get
dart run build_runner build --delete-conflicting-outputs

flutter run --dart-define-from-file=dart_defines.json
