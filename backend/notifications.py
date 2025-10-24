"""Notification utilities."""
from __future__ import annotations

import uuid
from datetime import datetime

from . import db


def queue_notification(user_id: str, message: str, *, league_id: str | None = None, kind: str = "info") -> str:
    notification_id = str(uuid.uuid4())
    db.execute(
        """
        INSERT INTO notifications (id, user_id, league_id, type, message)
        VALUES (?, ?, ?, ?, ?)
        """,
        (notification_id, user_id, league_id, kind, message),
    )
    return notification_id


def pending_notifications(user_id: str) -> list[dict]:
    rows = db.query_all(
        "SELECT * FROM notifications WHERE user_id = ? AND delivered = 0 ORDER BY created_at DESC",
        (user_id,),
    )
    return [dict(row) for row in rows]


def mark_delivered(notification_id: str) -> None:
    db.execute("UPDATE notifications SET delivered = 1 WHERE id = ?", (notification_id,))


def schedule_lineup_deadline_alert(user_id: str, league_id: str, deadline: datetime) -> str:
    return queue_notification(
        user_id,
        message=f"Set your lineup before {deadline.isoformat()}!",
        league_id=league_id,
        kind="lineup-deadline",
    )
