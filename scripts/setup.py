"""Setup helper: apply migrations, seed demo data, generate changelog."""
from __future__ import annotations

import os
from pathlib import Path

from backend import db, demo
from tools.generate_changelog import main as build_changelog


def run() -> None:
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if not line or line.strip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key, value)
    db.run_migrations()
    demo.seed_demo_content()
    build_changelog()


if __name__ == "__main__":
    run()
