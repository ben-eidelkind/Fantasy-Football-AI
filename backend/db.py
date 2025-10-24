"""Database utilities built on sqlite3."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import get_settings

_connection_cache: dict[str, sqlite3.Connection] = {}


def _ensure_connection() -> sqlite3.Connection:
    settings = get_settings()
    path = Path(settings.database_url)
    path.parent.mkdir(parents=True, exist_ok=True)
    cached = _connection_cache.get(settings.database_url)
    if cached is not None:
        return cached
    conn = sqlite3.connect(
        settings.database_url,
        detect_types=sqlite3.PARSE_DECLTYPES,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    _connection_cache[settings.database_url] = conn
    return conn


@contextmanager
def get_cursor() -> Iterator[sqlite3.Cursor]:
    conn = _ensure_connection()
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


def query_all(query: str, params: tuple | list | None = None) -> list[sqlite3.Row]:
    if params is None:
        params = ()
    with get_cursor() as cursor:
        cursor.execute(query, params)
        return cursor.fetchall()


def query_one(query: str, params: tuple | list | None = None) -> sqlite3.Row | None:
    rows = query_all(query, params)
    return rows[0] if rows else None


def execute(query: str, params: tuple | list | None = None) -> None:
    if params is None:
        params = ()
    with get_cursor() as cursor:
        cursor.execute(query, params)


def executemany(query: str, seq: list[tuple]) -> None:
    with get_cursor() as cursor:
        cursor.executemany(query, seq)


def run_migrations() -> None:
    """Apply SQL migrations in order."""
    migrations_dir = Path(__file__).resolve().parents[1] / "migrations"
    paths = sorted(p for p in migrations_dir.glob("*.sql"))
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            sql = handle.read()
        with get_cursor() as cursor:
            cursor.executescript(sql)
