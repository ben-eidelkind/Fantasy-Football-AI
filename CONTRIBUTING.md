# Contributing

Thank you for improving Fantasy Football AI! This project is designed for deterministic analytics and reproducible tests. Please follow the steps below when contributing:

1. **Discuss changes** – open an issue describing the enhancement or bug fix.
2. **Branch naming** – use `feature/<topic>` or `fix/<topic>`.
3. **Environment** – copy `.env.template` to `.env` and run `python -m scripts.setup` before development.
4. **Coding standards** – Python 3.11, type hints, and functional separation between modules (`auth`, `espn`, `analysis`, etc.). Avoid introducing non-standard-library dependencies unless justified.
5. **Testing** – run `python -m tests.run_all` before submitting a PR. Ensure deterministic outcomes.
6. **Changelog** – update `WHAT'S-NEW.md` and regenerate `public/whats-new.json` using `python tools/generate_changelog.py`.
7. **Pull request** – fill out the PR template, include screenshots for UI changes, and link to related issues.

By submitting a contribution you agree to license your work under the MIT License.
