"""Feature flag helpers."""
from __future__ import annotations

from . import db


def get_flags_for_user(user_id: str) -> dict[str, bool]:
    rows = db.query_all(
        "SELECT flag, enabled FROM feature_flags WHERE user_id = ?",
        (user_id,),
    )
    return {row["flag"]: bool(row["enabled"]) for row in rows}


def set_flag(user_id: str, flag: str, enabled: bool) -> None:
    db.execute(
        "INSERT OR REPLACE INTO feature_flags (user_id, flag, enabled) VALUES (?, ?, ?)",
        (user_id, flag, int(enabled)),
    )
