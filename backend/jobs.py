"""Background job scheduler."""
from __future__ import annotations

import logging
import random
import threading
import time
from datetime import datetime, timedelta

from . import analysis, db
from .config import get_settings
from .notifications import queue_notification

LOGGER = logging.getLogger(__name__)


class JobThread(threading.Thread):
    daemon = True

    def __init__(self, interval: float, target, name: str) -> None:
        super().__init__(target=self._run_wrapper, name=name)
        self.interval = interval
        self._target = target
        self._stop_event = threading.Event()

    def _run_wrapper(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._target()
            except Exception as exc:  # pragma: no cover - logging side effect
                LOGGER.exception("Job %s failed: %s", self.name, exc)
            self._stop_event.wait(self.interval)

    def stop(self) -> None:
        self._stop_event.set()


_threads: list[JobThread] = []


def refresh_projections() -> None:
    rows = db.query_all("SELECT DISTINCT player_id, week FROM projections")
    for row in rows:
        projection = analysis.blend_projections(row["player_id"], row["week"])
        db.execute(
            "UPDATE projections SET projected_points = ?, floor = ?, ceiling = ?, updated_at = ? WHERE player_id = ? AND week = ? AND source = ?",
            (
                projection.projected_points,
                projection.floor,
                projection.ceiling,
                datetime.utcnow().isoformat(),
                projection.player_id,
                projection.week,
                "blended",
            ),
        )


def refresh_injuries() -> None:
    updates = {
        "QUESTIONABLE": ["player-004"],
    }
    for status, players in updates.items():
        for player_id in players:
            db.execute(
                "UPDATE players SET injury_status = ? WHERE id = ?",
                (status, player_id),
            )


def send_pre_kickoff_alerts() -> None:
    now = datetime.utcnow()
    rows = db.query_all(
        """
        SELECT leagues.id as league_id, league_members.user_id as user_id
        FROM leagues
        JOIN league_members ON league_members.league_id = leagues.id
        WHERE leagues.is_active = 1
        """,
    )
    for row in rows:
        queue_notification(row["user_id"], "Lineup check: kickoff approaching", league_id=row["league_id"], kind="alert")


def run_all_jobs_once() -> None:
    refresh_projections()
    refresh_injuries()
    send_pre_kickoff_alerts()


def start_scheduler() -> None:
    settings = get_settings()
    if not settings.background_jobs_enabled:
        LOGGER.info("Background jobs disabled via config")
        return
    if _threads:
        return
    _threads.extend(
        [
            JobThread(60 * 60 * 24, refresh_projections, "nightly-projections"),
            JobThread(60 * 60, refresh_injuries, "hourly-injuries"),
            JobThread(60 * 30, send_pre_kickoff_alerts, "pre-kickoff-alerts"),
        ]
    )
    for thread in _threads:
        thread.start()


def stop_scheduler() -> None:
    for thread in _threads:
        thread.stop()
    for thread in _threads:
        thread.join(timeout=1)
    _threads.clear()
