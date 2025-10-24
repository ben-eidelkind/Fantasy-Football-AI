# Security overview

Fantasy Football AI prioritizes user consent, token safety, and principle-of-least-privilege design.

## Identity and sessions

- Passwordless email codes – ephemeral 6-digit codes stored in `login_tokens` with 15-minute TTL and one-time use.
- Sessions – opaque 256-bit tokens stored in `sessions` with configurable TTL (72h default). Stored in the browser via localStorage.
- Revocation – `/api/auth/logout` deletes the active session server-side; demo mode sessions may be recreated as needed.

## ESPN connection

- Auth state – `espn_credentials.provider_state` tracks pending auth flows to prevent replay.
- Stored tokens – `espn_credentials.access_token` / `refresh_token` hold only the minimum ESPN session fields required to call fantasy endpoints.
- Revocation – `/settings` exposes a reconnect button that creates a new state and overwrites the stored tokens. Administrators can delete the row in `espn_credentials` for immediate revocation.
- Mock provider – deterministic data used locally and in CI so no real ESPN credentials are needed.

## Data access & authorization

- League access is always joined through `league_members`. Users only see data linked to their user ID.
- Demo accounts are flagged (`users.is_demo=1`) and operate against fixture data.
- Feature flags gate advanced analytics and experimental flows per-user.

## Storage & encryption

- SQLite database lives on disk (path configurable). For production, place it on encrypted volumes.
- Access/refresh tokens can be encrypted at rest by overriding `DATABASE_URL` to point to an encrypted SQLite implementation or by wrapping the getters/setters in `backend/espn.py`.

## Input validation & error handling

- JSON APIs validate presence of required fields and respond with 400 for invalid requests.
- All DB operations run with `PRAGMA foreign_keys=ON` to enforce relational integrity.
- Deterministic random seeds ensure reproducible analytics without leaking data across users.

## Vulnerability reporting

Please open a security advisory or email `security@fantasy-football.ai`. Do not file public issues for sensitive vulnerabilities.
