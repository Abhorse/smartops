.PHONY: backend mobile backend-neon mobile-google test-backend test-mobile init-neon-db mobile-vercel mobile-config

backend:
	./scripts/start-backend.sh

# Local backend using backend/.env (Neon DATABASE_URL, GOOGLE_CLIENT_ID, etc.)
backend-neon:
	./scripts/start-backend.sh

mobile:
	./scripts/start-mobile.sh

# Regenerate mobile/dart_defines.json from backend/.env (then restart the app — hot reload is not enough)
mobile-config:
	./scripts/sync-mobile-dart-defines.sh

# One-time: create tables + roles on Neon (same DATABASE_URL as Vercel)
init-neon-db:
	./scripts/init-neon-db.sh

# Point mobile app at Vercel backend (override API_BASE_URL in backend/.env to customize)
mobile-vercel:
	APP_ENV=staging AUTH_DEV_MODE=false API_BASE_URL=$${API_BASE_URL:-https://ab.smartops1.vercel.app} ./scripts/sync-mobile-dart-defines.sh
	APP_ENV=staging AUTH_DEV_MODE=false ./scripts/start-mobile.sh

# Mobile with Google Sign-In (reads GOOGLE_CLIENT_ID from backend/.env)
mobile-google:
	AUTH_DEV_MODE=false ./scripts/start-mobile.sh

test-backend:
	cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && pytest

test-mobile:
	cd mobile && flutter pub get && dart run build_runner build --delete-conflicting-outputs && flutter test
