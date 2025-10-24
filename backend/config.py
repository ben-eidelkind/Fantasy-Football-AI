"""Application configuration helpers."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_url: str
    demo_mode_enabled: bool
    telemetry_enabled: bool
    metrics_port: int
    auth_token_ttl_hours: int
    feature_flags: tuple[str, ...]
    changelog_path: Path
    whats_new_url: str
    background_jobs_enabled: bool
    projection_sources: tuple[str, ...]


def _env_bool(key: str, default: bool) -> bool:
    value = os.environ.get(key)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def get_settings() -> Settings:
    root = Path(__file__).resolve().parents[1]
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        database_url = str(root / "data" / "app.db")
    return Settings(
        database_url=database_url,
        demo_mode_enabled=_env_bool("DEMO_MODE_ENABLED", True),
        telemetry_enabled=_env_bool("TELEMETRY_ENABLED", True),
        metrics_port=int(os.environ.get("METRICS_PORT", "9100")),
        auth_token_ttl_hours=int(os.environ.get("AUTH_TOKEN_TTL_HOURS", "72")),
        feature_flags=(
            "demo-mode",
            "advanced-analytics",
            "experimental-trade-lab",
        ),
        changelog_path=root / "WHAT'S-NEW.md",
        whats_new_url=os.environ.get("WHATS_NEW_URL", "/whats-new"),
        background_jobs_enabled=_env_bool("BACKGROUND_JOBS_ENABLED", True),
        projection_sources=(
            "fantasycalc",
            "nfldata",
            "mock-blend",
        ),
    )
