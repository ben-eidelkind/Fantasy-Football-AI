# Fantasy Football AI

Fantasy Football AI is a fully self-contained web application that delivers roster intelligence, waiver insights, trade frameworks, matchup simulations, and notifications for ESPN fantasy leagues. It features zero-touch onboarding, an interactive dashboard, demo mode, typed data contracts, deterministic analytics, and background jobs.

## Highlights

- **Zero-touch onboarding** – passwordless email codes or one-click Demo Mode.
- **Secure ESPN connection** – mock provider locally with the ability to swap for live tokens.
- **Multi-league dashboard** – matchup odds, lineup deltas, waiver gems, actionable to-dos.
- **Season-long utilities** – lineup optimizer, waiver scores, trade lab, playoff heatmaps.
- **Analytics** – blended projections, Monte Carlo matchup sims, roster optimizer heuristics.
- **Background jobs** – nightly projection refresh, hourly injury sync, kickoff alerts.
- **Operational maturity** – migrations, seeds, telemetry hooks, CI workflows, docs, and tests.

## Quick start

```bash
# 1. Create environment configuration
cp .env.template .env

# 2. Run migrations and seed demo data
python -m scripts.setup

# 3. Launch the web server
python -m backend.server
```

The app will be available at [http://localhost:8787](http://localhost:8787). Sign in with your email (codes are shown in-app for local development) or hit **Launch Demo** to load seeded leagues instantly.

## One-command workflows

- **Start app with demo data:** `python -m scripts.setup && python -m backend.server`
- **Run the full deterministic test suite:** `python -m tests.run_all`
- **Generate the in-app changelog:** `python tools/generate_changelog.py`

## Project structure

```
backend/         Core services, API handlers, analytics, integrations
frontend/        (Reserved for future component extraction)
public/          Static assets served by the backend (SPA, styles, changelog JSON)
migrations/      SQLite migrations (relational schema)
scripts/         Setup, seeding, and tooling entry points
tests/           Unit, integration, and e2e coverage
.github/         CI workflows and contribution templates
```

For deeper documentation see:

- [SETUP.md](SETUP.md) – onboarding, configuration, ESPN auth, demo data.
- [ARCHITECTURE.md](ARCHITECTURE.md) – system diagram, modules, data flow.
- [DATA-CONTRACTS.md](DATA-CONTRACTS.md) – typed interfaces and validation rules.
- [SECURITY.md](SECURITY.md) – token storage, revocation, secure session handling.
- [WHAT'S-NEW.md](WHAT'S-NEW.md) – human-readable changelog, auto-synced to the UI.

## License

This project is released under the MIT License. Contributions are welcome – review [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
