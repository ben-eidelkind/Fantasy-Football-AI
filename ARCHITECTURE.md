# Architecture

## High-level diagram

```
┌──────────────────────┐        ┌────────────────────┐
│  Public SPA (Vanilla │  HTTP  │  backend.server    │
│  JS + Tailwind-lite) ├────────►  (ThreadingHTTP)   │
└──────────────────────┘        │   ├─ auth          │
                                │   ├─ espn provider │
                                │   ├─ analytics     │
                                │   ├─ jobs          │
                                │   └─ notifications │
                                └────────┬───────────┘
                                         │
                                         ▼
                                ┌────────────────────┐
                                │ SQLite (app.db)    │
                                │  migrations/       │
                                └────────────────────┘
```

## Modules

### `backend.server`

- HTTP gateway that serves static assets and JSON APIs.
- Applies migrations, seeds demo data, and boots job scheduler on startup.
- Routes all `/api/*` requests with explicit handlers that enforce session auth.

### `backend.auth`

- Passwordless email authentication with six-digit codes stored in `login_tokens`.
- Session issuing, lookup, and revocation helpers.
- Demo account bootstrap toggles feature flags for analytics modules.

### `backend.espn`

- Provider abstraction for ESPN integrations.
- `MockESPNProvider` supplies deterministic data for local + CI.
- `RealESPNProvider` placeholder ready to capture session cookies/tokens via hosted auth.
- Sync pipeline persists leagues, teams, and membership relationships.

### `backend.analysis`

- Deterministic analytics (lineup optimizer, waiver scores, trade proposals, simulation engine).
- Weighted projection blending across fixture sources.
- Monte Carlo simulation with seeded RNG for reproducible tests.

### `backend.jobs`

- Scheduler built on daemon threads.
- Nightly projection refresh, hourly injury updates, and 30-minute kickoff alerts.
- `run_all_jobs_once()` used by integration tests and cron equivalents.

### `backend.notifications`

- In-app notification queue stored in the database.
- Convenience helpers for lineup deadline reminders.

### `backend.demo`

- Loads fixture data into the relational schema (users, leagues, teams, rosters, projections).

## Data flow

1. User signs in (or enters demo mode) → session token issued.
2. User begins ESPN auth → provider stores state and issues auth URL.
3. UI completes auth → tokens persisted, leagues synced to DB.
4. Dashboard requests data → analytics modules load from DB and compute recommendations.
5. Background jobs run periodically to refresh projections and enqueue notifications.

## Background jobs

| Job | Cadence | Responsibility |
| --- | ------- | -------------- |
| `nightly-projections` | 24h | Re-blend projections, update `projections` table. |
| `hourly-injuries` | 1h | Update `players.injury_status` with latest status markers. |
| `pre-kickoff-alerts` | 30m | Queue lineup notifications for active leagues. |

## Telemetry

- Standard library logging captures request summaries (`AppHandler.log_message`).
- Hooks exposed via `config.Settings` to enable/disable telemetry in different environments.
- Jobs log errors without crashing the scheduler threads.

## Feature flags

Flags stored in `feature_flags` table (per user) and surfaced in `/api/me`.

| Flag | Purpose |
| ---- | ------- |
| `demo-mode` | Enables seeded data flows for the demo user. |
| `advanced-analytics` | Gates heavy simulations (enabled by default). |
| `experimental-trade-lab` | Toggle for advanced trade UI modules. |

## Command palette (optional)

The SPA exposes keyboard-friendly navigation via focusable buttons. A full Command-K launcher can be added by extending `public/app.js` – hooks are prepared via `navigate(view)`.
