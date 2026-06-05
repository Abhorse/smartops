---
name: Google Auth Session Plan
overview: Switch MVP authentication from phone OTP to Google Sign-In only (zero SMS cost), document how mobile JWT sessions work with offline-first SmartOps, and defer OTP to Phase 2.
todos:
  - id: auth-sessions-doc
    content: Create docs/auth-sessions.md — Google OAuth flow, JWT session lifecycle, offline behavior, secure storage
    status: completed
  - id: update-architecture-auth
    content: Update docs/architecture.md — replace OTP diagram with Google auth + mobile session lifecycle section
    status: completed
  - id: update-database-auth
    content: Update docs/database-design.md — google_sub, nullable phone, auth_provider enum
    status: completed
  - id: update-mvp-auth
    content: Update docs/mvp-requirements.md — Google Sign-In user stories, onboarding flow, non-goals
    status: completed
  - id: update-tech-revenue-auth
    content: Update docs/tech-stack.md and docs/revenue-model.md — Google-first auth, remove MSG91 from MVP costs
    status: completed
isProject: false
---

# Google Auth + Mobile Session Plan

## Your request (confirmed)

- **Phase 1 (MVP):** Google Sign-In only — no OTP, no MSG91 cost
- **Phase 2+:** Add phone OTP for users who prefer it
- **Also:** Explain how login sessions work in the mobile app

---

## How mobile login sessions work (SmartOps model)

Mobile apps do **not** use browser cookies like websites. SmartOps uses **token-based sessions** stored securely on the device.

```mermaid
sequenceDiagram
  participant User
  participant App as FlutterApp
  participant Secure as SecureStorage
  participant Google as GoogleOAuth
  participant API as FastAPI
  participant DB as PostgreSQL

  User->>App: Tap Sign in with Google
  App->>Google: OAuth flow (requires internet)
  Google-->>App: Google ID token
  App->>API: POST /auth/google {id_token}
  API->>Google: Verify token signature
  API->>DB: Find or create user by google_sub/email
  API-->>App: access_token + refresh_token
  App->>Secure: Store tokens + device_id
  App->>User: Dashboard (online)

  Note over App,Secure: Later — app reopened offline
  App->>Secure: Read access_token
  App->>App: Load dashboard from Isar (no network needed)

  Note over App,API: Access token expired, network available
  App->>API: POST /auth/refresh {refresh_token}
  API-->>App: New access_token

  Note over App,API: Access expired, offline
  App->>User: Local data works; sync blocked until online
```

### Two tokens, two jobs

| Token | Lifetime | Stored where | Purpose |
|---|---|---|---|
| **Access token** (JWT) | ~15 minutes | `flutter_secure_storage` | Sent on every API call: `Authorization: Bearer ...` |
| **Refresh token** (opaque) | ~30 days, device-bound | `flutter_secure_storage` | Used only to get a new access token; never sent on every request |

The **session** = the pair of tokens + `device_id` + cached user/org context. It is **not** a server-side session cookie.

### What happens in each scenario

| Scenario | Behavior |
|---|---|
| **First login** | Requires internet (Google OAuth + backend token exchange) |
| **App reopened (online, valid access token)** | Instant entry; optional background sync |
| **App reopened (offline, valid access token)** | Full offline access to Isar data; sync paused |
| **App reopened (offline, expired access token)** | **Local data still works** — user can add expenses, mark attendance, etc. Sync and refresh wait until network returns |
| **App reopened (online, expired access token)** | Silent refresh via refresh token → new access token → sync resumes |
| **Refresh token expired (30+ days offline)** | User must sign in with Google again (one-time internet login) |
| **Logout** | Revoke refresh token on server; wipe secure storage + local Isar DB |

This aligns with your offline-first goal in [docs/app-details.md](docs/app-details.md): business operations never stop because of auth — only **cloud sync** requires a valid access token.

### Where tokens live (never in plain storage)

```
flutter_secure_storage
├── access_token
├── refresh_token
├── device_id          # UUID generated on first install
└── active_org_id      # last selected organization
```

- **Android:** Encrypted SharedPreferences / Keystore
- **iOS:** Keychain

Do **not** store tokens in `SharedPreferences`, Isar, or logs.

### Server-side session tracking

Even with JWTs, the backend tracks sessions in [`refresh_tokens`](docs/database-design.md) table:

- `user_id`, `device_id`, `token_hash`, `expires_at`, `revoked_at`
- Enables: logout from device, single-device MVP policy, future "active sessions" UI
- Access tokens are stateless (JWT); refresh tokens are stateful (DB lookup)

---

## Auth strategy change: Google first, OTP later

### Why this fits your cost goal

| Method | MVP cost | Internet required at login |
|---|---|---|
| Phone OTP (MSG91) | ~₹0.10–0.20 per SMS | Yes |
| Google Sign-In | **Free** | Yes |
| Email/password | Free | Yes |

Google-only MVP removes MSG91 entirely from Phase 1 infra budget ([docs/revenue-model.md](docs/revenue-model.md) currently lists ₹1,000–₹3,000/mo for OTP).

### MVP implementation (Google only)

**Mobile ([`mobile/`](mobile/) — future):**
- Package: `google_sign_in`
- Flow: Google account picker → ID token → POST to backend

**Backend ([`backend/`](backend/) — future):**
- `POST /api/v1/auth/google` — body: `{ "id_token": "..." }`
- Verify with `google-auth` library (Google public keys)
- Upsert user by `google_sub` (stable Google user ID) + `email`
- Return `{ access_token, refresh_token, user, organizations }`
- `POST /api/v1/auth/refresh` — unchanged
- `POST /api/v1/auth/logout` — revoke refresh token

**User table additions** ([docs/database-design.md](docs/database-design.md)):

| Column | Purpose |
|---|---|
| `google_sub` | VARCHAR UNIQUE — primary identity for Google users |
| `email` | From Google profile (required for Google-only MVP) |
| `phone` | NULL in MVP; populated when OTP added in Phase 2 |

Make `phone` nullable (currently NOT NULL in schema doc).

### Phase 2: Add OTP (keep Google)

| Phase | Auth methods |
|---|---|
| MVP v1.0 | Google Sign-In only |
| v2.0 | Google + Phone OTP (MSG91) |
| v3.0 | + Apple Sign-In (if iOS user base grows), SSO for enterprise |

Users who sign in with Google first can **link phone number** later in settings (optional account linking).

### Tradeoff to accept (Google-only MVP)

- Some Indian SMB owners use non-Gmail email or share a shop phone — they cannot use the app until OTP ships in v2
- Mitigation: communicate clearly in marketing ("Sign in with Google"); prioritize OTP in v2 based on beta feedback

---

## Documentation updates required

Update these files to reflect Google-first auth (do **not** edit the plan file):

### 1. [docs/tech-stack.md](docs/tech-stack.md)

- Auth row: `Google Sign-In (MVP)` primary; `Phone OTP` → Phase 2
- Remove MSG91 from MVP dependencies; add `google_sign_in`, `google-auth`
- Update decision log: Google-first for zero auth cost
- Move MSG91 to Phase 2 section

### 2. [docs/architecture.md](docs/architecture.md)

- Replace OTP sequence diagram with Google OAuth flow (diagram above)
- Add **Mobile Session Lifecycle** section (token storage, offline grace, refresh behavior)
- Update auth API routes: `/auth/google`, `/auth/refresh`, `/auth/logout`
- Update risks: remove OTP delivery failure; add "Google account required"

### 3. [docs/database-design.md](docs/database-design.md)

- `users.phone` → nullable
- Add `users.google_sub` VARCHAR UNIQUE
- Add `users.auth_provider` ENUM (`google`, `otp` — default `google` for MVP)
- Note Phase 2 phone linking table optional: `user_auth_providers`

### 4. [docs/mvp-requirements.md](docs/mvp-requirements.md)

- Replace AUTH-01/AUTH-02 user stories with Google Sign-In stories
- Update onboarding flow: `Google Sign-In → Language → Business profile`
- Move phone invite (AUTH-05) to P2 or change to email invite
- Remove MSG91 from non-goals; add "Phone OTP login" to explicit non-goals (v1.0)
- Update technical acceptance: auth endpoints except `/auth/google`, `/auth/refresh`

### 5. [docs/revenue-model.md](docs/revenue-model.md)

- Remove MSG91 from MVP infra cost table (or mark ₹0 for MVP)
- Add note: auth infra cost = ₹0 in MVP

### 6. Optional: [docs/auth-sessions.md](docs/auth-sessions.md) (new)

Standalone deep-dive on mobile sessions, token refresh, offline behavior, and security — keeps architecture doc shorter. Cross-link from other docs.

---

## Recommended session settings for SmartOps

| Setting | Value | Rationale |
|---|---|---|
| Access token TTL | 15 minutes | Limits exposure if stolen |
| Refresh token TTL | 30 days | Long offline periods without re-login |
| Offline grace | Unlimited local access while refresh token exists locally | Offline-first UX |
| Refresh strategy | Proactive refresh when app foregrounds + network available | Avoid sync failures |
| Single device (MVP) | New login revokes previous device refresh token | Matches sync v1 policy |
| Logout | Server revoke + wipe local DB | Shared device safety |

---

## Implementation order

1. Add `docs/auth-sessions.md` (session explanation + Google flow) — reference doc for team
2. Update `architecture.md` auth section + session lifecycle
3. Update `database-design.md` user identity fields
4. Update `mvp-requirements.md` user stories and flows
5. Update `tech-stack.md` and `revenue-model.md` cost/auth tables

No application code changes in this step — documentation only, matching the completed planning phase.
