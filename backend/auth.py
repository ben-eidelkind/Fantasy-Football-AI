"""Authentication helpers providing email-code login and demo accounts."""
from __future__ import annotations

import secrets
import string
import uuid
from datetime import datetime, timedelta
from typing import Any

from .config import get_settings
from . import db


CODE_ALPHABET = string.digits
CODE_LENGTH = 6


def _generate_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def request_login_code(email: str) -> dict[str, Any]:
    """Create a one-time login code; return payload for notifications/tests."""
    code = _generate_code()
    token_id = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(minutes=15)
    db.execute(
        """
        INSERT INTO login_tokens (id, email, code, expires_at)
        VALUES (?, ?, ?, ?)
        """,
        (token_id, email.lower(), code, expires_at.isoformat()),
    )
    return {"token_id": token_id, "code": code, "expires_at": expires_at.isoformat()}


def _ensure_user(email: str, *, is_demo: bool = False) -> str:
    row = db.query_one("SELECT id FROM users WHERE email = ?", (email.lower(),))
    if row:
        return str(row["id"])
    user_id = str(uuid.uuid4())
    db.execute(
        """
        INSERT INTO users (id, email, name, is_demo)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, email.lower(), email.split("@")[0].title(), int(is_demo)),
    )
    return user_id


def verify_login_code(email: str, code: str) -> dict[str, Any] | None:
    row = db.query_one(
        """
        SELECT id, code, expires_at, consumed
        FROM login_tokens
        WHERE email = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (email.lower(),),
    )
    if not row:
        return None
    if row["consumed"]:
        return None
    if row["code"] != code:
        return None
    expires_at = datetime.fromisoformat(row["expires_at"])
    if expires_at < datetime.utcnow():
        return None
    db.execute("UPDATE login_tokens SET consumed = 1 WHERE id = ?", (row["id"],))
    user_id = _ensure_user(email)
    session = _create_session(user_id)
    return {"user_id": user_id, "session": session}


def create_demo_user() -> dict[str, Any]:
    user_id = _ensure_user("demo@local", is_demo=True)
    db.execute(
        "INSERT OR IGNORE INTO feature_flags (user_id, flag, enabled) VALUES (?, ?, 1)",
        (user_id, "demo-mode"),
    )
    session = _create_session(user_id)
    return {"user_id": user_id, "session": session}


def _create_session(user_id: str) -> dict[str, str]:
    token = secrets.token_urlsafe(32)
    session_id = str(uuid.uuid4())
    ttl = timedelta(hours=get_settings().auth_token_ttl_hours)
    expires_at = datetime.utcnow() + ttl
    db.execute(
        """
        INSERT INTO sessions (id, user_id, token, expires_at)
        VALUES (?, ?, ?, ?)
        """,
        (session_id, user_id, token, expires_at.isoformat()),
    )
    return {"token": token, "expires_at": expires_at.isoformat()}


def get_user_by_session(token: str) -> dict[str, Any] | None:
    row = db.query_one(
        """
        SELECT sessions.user_id, users.email, users.name, users.is_demo
        FROM sessions
        JOIN users ON users.id = sessions.user_id
        WHERE sessions.token = ?
        """,
        (token,),
    )
    if not row:
        return None
    return {
        "id": row["user_id"],
        "email": row["email"],
        "name": row["name"],
        "is_demo": bool(row["is_demo"]),
    }


def revoke_session(token: str) -> None:
    db.execute("DELETE FROM sessions WHERE token = ?", (token,))
