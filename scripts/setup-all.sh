#!/usr/bin/env bash
# Full SmartOps setup: Neon schema, mobile config for Vercel, optional Vercel deploy.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERCEL_URL="${API_BASE_URL:-https://ab.smartops1.vercel.app}"

echo "==> [1/4] Initialize Neon database (tables + roles)"
"$ROOT/scripts/init-neon-db.sh"

echo ""
echo "==> [2/4] Configure mobile app for Vercel backend"
APP_ENV=staging AUTH_DEV_MODE=false API_BASE_URL="$VERCEL_URL" \
  "$ROOT/scripts/sync-mobile-dart-defines.sh"

echo ""
echo "==> [3/4] Push env vars + deploy to Vercel (skip with SKIP_VERCEL=1)"
if [ "${SKIP_VERCEL:-0}" = "1" ]; then
  echo "    Skipped (SKIP_VERCEL=1). Set env vars manually in Vercel dashboard."
else
  if [ -n "${VERCEL_TOKEN:-}" ] || [ -d "$HOME/.vercel" ]; then
    "$ROOT/scripts/setup-vercel-env.sh" || {
      echo "    Vercel CLI deploy failed — set env vars in dashboard and redeploy from Git."
    }
  else
    echo "    No Vercel login/token. Run: npx vercel login"
    echo "    Then: VERCEL_TOKEN=... $ROOT/scripts/setup-vercel-env.sh"
    echo "    Or set env vars manually at https://vercel.com/ab-smart-ops-project/ab.smartops1/settings/environment-variables"
  fi
fi

echo ""
echo "==> [4/4] Verify deployment"
if command -v curl >/dev/null 2>&1; then
  curl -sS --max-time 30 "${VERCEL_URL}/api/v1/health" && echo "" || \
    echo "    Health check failed (deploy may still be building)."
fi

echo ""
echo "==> Setup complete"
echo "    Mobile config: mobile/assets/config/env.json"
echo "    Start app:     make mobile-google   (or flutter run from mobile/)"
echo "    API URL:       $VERCEL_URL"
