"""Demo data helpers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import db
from .auth import _ensure_user

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"


def load_json(name: str) -> Any:
    with (FIXTURE_ROOT / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def seed_demo_content() -> None:
    data = load_json("demo_leagues.json")
    rosters = load_json("demo_rosters.json")

    # Ensure users exist
    for league in data["leagues"]:
        for team in league["teams"]:
            _ensure_user(team["owner_email"], is_demo=True)

    for league in data["leagues"]:
        db.execute(
            """
            INSERT OR REPLACE INTO leagues (id, user_owner_id, espn_league_id, season, name, scoring_type, is_active)
            VALUES (?, NULL, ?, ?, ?, ?, 1)
            """,
            (
                league["id"],
                league.get("espn_league_id"),
                league["season"],
                league["name"],
                league.get("scoring_type", "PPR"),
            ),
        )
        for team in league["teams"]:
            owner = db.query_one("SELECT id FROM users WHERE email = ?", (team["owner_email"],))
            db.execute(
                """
                INSERT OR REPLACE INTO teams (id, league_id, name, owner_user_id, wins, losses, ties, points_for, points_against, playoff_odds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    team["id"],
                    league["id"],
                    team["name"],
                    owner["id"] if owner else None,
                    team["wins"],
                    team["losses"],
                    team["ties"],
                    team["points_for"],
                    team["points_against"],
                    team.get("playoff_odds", 0.5),
                ),
            )
            if owner:
                db.execute(
                    """
                    INSERT OR IGNORE INTO league_members (id, league_id, user_id, team_id, role)
                    VALUES (?, ?, ?, ?, 'manager')
                    """,
                    (f"member-{owner['id']}-{league['id']}", league["id"], owner["id"], team["id"]),
                )
        for matchup in league.get("matchups", []):
            db.execute(
                """
                INSERT OR REPLACE INTO matchups (id, league_id, week, home_team_id, away_team_id, home_score, away_score, kickoff)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    matchup["id"],
                    league["id"],
                    matchup["week"],
                    matchup["home_team_id"],
                    matchup["away_team_id"],
                    matchup.get("home_score", 0.0),
                    matchup.get("away_score", 0.0),
                    matchup.get("kickoff"),
                ),
            )

    for player in data["players"]:
        db.execute(
            """
            INSERT OR REPLACE INTO players (id, name, position, team, bye_week, injury_status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                player["id"],
                player["name"],
                player["position"],
                player.get("team"),
                player.get("bye_week"),
                player.get("injury_status", "ACTIVE"),
            ),
        )

    for roster in rosters["rosters"]:
        db.execute(
            """
            INSERT OR REPLACE INTO rosters (id, league_id, team_id, week)
            VALUES (?, ?, ?, ?)
            """,
            (
                roster["id"],
                roster["league_id"],
                roster["team_id"],
                roster["week"],
            ),
        )
        for spot in roster["spots"]:
            db.execute(
                """
                INSERT OR REPLACE INTO roster_spots (id, roster_id, player_id, slot, status, projected_points, opponent, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{roster['id']}-{spot['player_id']}",
                    roster["id"],
                    spot["player_id"],
                    spot["slot"],
                    spot["status"],
                    spot["projected_points"],
                    spot.get("opponent"),
                    spot.get("notes", ""),
                ),
            )

    for projection in rosters["projections"]:
        db.execute(
            """
            INSERT OR REPLACE INTO projections (id, player_id, week, source, projected_points, floor, ceiling)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"proj-{projection['source']}-{projection['player_id']}-{projection['week']}",
                projection["player_id"],
                projection["week"],
                projection["source"],
                projection["projected_points"],
                projection["floor"],
                projection["ceiling"],
            ),
        )
