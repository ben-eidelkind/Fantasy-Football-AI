# Setup guide

This document walks through configuring, running, and testing Fantasy Football AI across local development, CI, and production.

## Prerequisites

- Python 3.11+
- No external dependencies are required; the app uses the Python standard library and ships with SQLite migrations and fixtures.

## Environment configuration

1. Copy the template and adjust values as needed:

   ```bash
   cp .env.template .env
   ```

2. Supported environment variables:

   | Name | Default | Description |
   | ---- | ------- | ----------- |
   | `DATABASE_URL` | `data/app.db` | Path to the SQLite database file. |
   | `DEMO_MODE_ENABLED` | `true` | Seeds demo data and enables demo login. |
   | `BACKGROUND_JOBS_ENABLED` | `true` | Runs projection refresh + alerts scheduler. |
   | `TELEMETRY_ENABLED` | `true` | Enables basic request logging/metrics hooks. |
   | `WHATS_NEW_URL` | `/whats-new` | Override for release notes link. |

## Bootstrapping the database

The project uses raw SQL migrations. Apply them and load demo fixtures using the helper script:

```bash
python -m scripts.setup
```

This command:

1. Loads environment variables from `.env` if present.
2. Applies all migrations from `migrations/` in lexical order.
3. Seeds demo leagues, teams, players, rosters, projections, and default feature flags.
4. Generates `public/whats-new.json` from `WHAT'S-NEW.md` for the UI.

## Running the web server

```bash
python -m backend.server
```

The server listens on `0.0.0.0:8787`. On startup it:

- Applies any pending migrations.
- Seeds demo data when `DEMO_MODE_ENABLED=true`.
- Starts background job threads for projections, injuries, and alerts.
- Serves the SPA from `public/` and JSON APIs under `/api`.

## ESPN authentication flow

1. Navigate to **Onboarding** and sign in with your email code (codes are shown inline for local dev).
2. Click **Sign in to ESPN**. The backend issues a state token and (in local/dev) uses the Mock provider.
3. The UI simulates the hosted login, then calls `/api/espn/complete` to save the mock session.
4. Click **Discover Leagues** to fetch deterministic mock leagues.
5. Select leagues and activate them – you are redirected to the dashboard with populated analytics.

To integrate with the real ESPN workflow, implement the cookie/token capture inside `backend/espn.py::RealESPNProvider.complete_auth` and set `provider: "real"` when calling `/api/espn/begin` from the UI. The storage, revocation, and syncing logic are already pluggable.

## Demo mode

Demo mode enables users to explore the entire experience without an ESPN account:

- The **Launch Demo** button signs in as `demo@local` and seeds the deterministic fixtures.
- Analytics, waivers, trades, projections, and simulations run entirely on local data.
- Tests and CI rely on the mock/demo data for deterministic results.

## Running tests

The project ships with unit, integration, and e2e coverage. Run the full suite via:

```bash
python -m tests.run_all
```

This executes:

1. Unit tests for analytics and scoring logic (`tests/unit`).
2. Integration tests for the ESPN provider, background jobs, and notifications (`tests/integration`).
3. E2E journey tests that exercise onboarding, demo mode, and league flows via the lightweight browser harness (`tests/e2e`).

Test reports are written to `artifacts/` (created automatically). CI uploads them as workflow artifacts.

## Background jobs

Jobs run in daemon threads within the web process. You can trigger them manually in isolation:

```bash
python -c "from backend import jobs; from backend import db, demo; db.run_migrations(); demo.seed_demo_content(); jobs.run_all_jobs_once()"
```

## Release notes workflow

1. Update `WHAT'S-NEW.md` with a new heading (e.g., `## v1.0.0`).
2. Run `python tools/generate_changelog.py` to refresh `public/whats-new.json`.
3. Commit both files; CI will display the changelog in `/whats-new` inside the app.

## Deployment

Fantasy Football AI is a simple Python process. Deploy by running `python -m backend.server` behind your reverse proxy of choice. Set `BACKGROUND_JOBS_ENABLED=false` if you prefer to run scheduled jobs externally (call `backend.jobs.run_all_jobs_once()` from cron).
