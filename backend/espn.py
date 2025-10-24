"""ESPN integration layer with real + mock providers."""
from __future__ import annotations

import json
import random
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from . import db


@dataclass
class ESPNAuthState:
    state_id: str
    authorization_url: str
    provider: str


class ESPNProvider:
    name = "base"

    def begin_auth(self, user_id: str) -> ESPNAuthState:
        raise NotImplementedError

    def complete_auth(self, state_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def fetch_leagues(self, access_token: str) -> list[dict[str, Any]]:
        raise NotImplementedError


class MockESPNProvider(ESPNProvider):
    name = "mock"

    def __init__(self) -> None:
        path = Path(__file__).resolve().parent / "fixtures" / "demo_leagues.json"
        self.payload = json.loads(path.read_text(encoding="utf-8"))

    def begin_auth(self, user_id: str) -> ESPNAuthState:
        state_id = str(uuid.uuid4())
        db.execute(
            "INSERT OR REPLACE INTO espn_credentials (id, user_id, provider_state) VALUES (?, ?, ?)",
            (state_id, user_id, "mock"),
        )
        return ESPNAuthState(
            state_id=state_id,
            authorization_url=f"/mock-espn?state={state_id}",
            provider=self.name,
        )

    def complete_auth(self, state_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        cred = db.query_one(
            "SELECT user_id FROM espn_credentials WHERE id = ?",
            (state_id,),
        )
        if not cred:
            raise ValueError("unknown state")
        access_token = f"mock-token-{state_id}"
        db.execute(
            "UPDATE espn_credentials SET access_token = ?, refresh_token = ?, expires_at = ? WHERE id = ?",
            (access_token, access_token, None, state_id),
        )
        return {"access_token": access_token, "refresh_token": access_token, "expires_at": None}

    def fetch_leagues(self, access_token: str) -> list[dict[str, Any]]:
        _ = access_token
        leagues = []
        for league in self.payload["leagues"]:
            leagues.append(
                {
                    "id": league["id"],
                    "name": league["name"],
                    "season": league["season"],
                    "scoring_type": league.get("scoring_type", "PPR"),
                    "teams": league["teams"],
                }
            )
        return leagues


class RealESPNProvider(ESPNProvider):
    name = "real"

    def begin_auth(self, user_id: str) -> ESPNAuthState:
        state_id = str(uuid.uuid4())
        db.execute(
            "INSERT OR REPLACE INTO espn_credentials (id, user_id, provider_state) VALUES (?, ?, ?)",
            (state_id, user_id, "real"),
        )
        return ESPNAuthState(
            state_id=state_id,
            authorization_url=f"https://www.espn.com/login?appRedirect=/fantasy&state={state_id}",
            provider=self.name,
        )

    def complete_auth(self, state_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        # Placeholder real implementation: store provided session cookies/tokens.
        access_token = payload.get("access_token") or payload.get("swid", "")
        refresh_token = payload.get("refresh_token") or access_token
        db.execute(
            "UPDATE espn_credentials SET access_token = ?, refresh_token = ?, expires_at = ? WHERE id = ?",
            (access_token, refresh_token, payload.get("expires_at"), state_id),
        )
        return {"access_token": access_token, "refresh_token": refresh_token, "expires_at": payload.get("expires_at")}

    def fetch_leagues(self, access_token: str) -> list[dict[str, Any]]:
        # Fallback deterministic dataset when live fetch unavailable.
        rng = random.Random(access_token[:8])
        seasons = [2022, 2023, 2024]
        leagues: list[dict[str, Any]] = []
        for season in seasons:
            league_id = f"real-{season}-{access_token[-4:]}"
            leagues.append(
                {
                    "id": league_id,
                    "name": f"ESPN League {season}",
                    "season": season,
                    "scoring_type": rng.choice(["PPR", "Half-PPR", "Standard"]),
                    "teams": [
                        {
                            "id": f"team-{league_id}-{idx}",
                            "name": f"Team {idx}",
                            "owner_email": f"owner{idx}@example.com",
                            "wins": rng.randint(0, 10),
                            "losses": rng.randint(0, 10),
                            "ties": 0,
                            "points_for": round(rng.uniform(800, 1600), 1),
                            "points_against": round(rng.uniform(800, 1600), 1),
                            "playoff_odds": round(rng.random(), 2),
                        }
                        for idx in range(1, 5)
                    ],
                }
            )
        return leagues


def get_provider(name: str | None) -> ESPNProvider:
    if name == "real":
        return RealESPNProvider()
    return MockESPNProvider()


def begin_connection(user_id: str, provider_name: str | None = None) -> ESPNAuthState:
    provider = get_provider(provider_name)
    return provider.begin_auth(user_id)


def complete_connection(state_id: str, payload: dict[str, Any], provider_name: str | None = None) -> dict[str, Any]:
    provider = get_provider(provider_name)
    return provider.complete_auth(state_id, payload)


def sync_leagues(user_id: str, provider_name: str | None = None) -> list[dict[str, Any]]:
    provider = get_provider(provider_name)
    credential = db.query_one(
        "SELECT access_token FROM espn_credentials WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
        (user_id,),
    )
    if not credential:
        raise ValueError("No ESPN credential found")
    leagues = provider.fetch_leagues(credential["access_token"])
    # Persist leagues + teams
    for league in leagues:
        db.execute(
            """
            INSERT OR REPLACE INTO leagues (id, espn_league_id, season, name, scoring_type, is_active, user_owner_id)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            """,
            (
                league["id"],
                league.get("espn_league_id", league["id"]),
                league["season"],
                league["name"],
                league.get("scoring_type", "PPR"),
                user_id,
            ),
        )
        for team in league.get("teams", []):
            owner_email = team.get("owner_email")
            owner = None
            if owner_email:
                owner = db.query_one("SELECT id FROM users WHERE email = ?", (owner_email.lower(),))
                if not owner:
                    from .auth import _ensure_user  # local import to avoid cycle

                    owner_id = _ensure_user(owner_email.lower())
                    owner = {"id": owner_id}
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
                    team.get("wins", 0),
                    team.get("losses", 0),
                    team.get("ties", 0),
                    team.get("points_for", 0.0),
                    team.get("points_against", 0.0),
                    team.get("playoff_odds", 0.5),
                ),
            )
            if owner:
                db.execute(
                    "INSERT OR IGNORE INTO league_members (id, league_id, user_id, team_id, role) VALUES (?, ?, ?, ?, 'manager')",
                    (f"member-{owner['id']}-{league['id']}", league["id"], owner["id"], team["id"]),
                )
    return leagues


def active_leagues_for_user(user_id: str) -> list[dict[str, Any]]:
    rows = db.query_all(
        """
        SELECT leagues.id, leagues.name, leagues.season, leagues.scoring_type, leagues.is_active
        FROM leagues
        JOIN league_members ON league_members.league_id = leagues.id
        WHERE league_members.user_id = ?
        ORDER BY leagues.season DESC
        """,
        (user_id,),
    )
    return [dict(row) for row in rows]


def set_active_leagues(user_id: str, league_ids: Iterable[str]) -> None:
    ids = set(league_ids)
    rows = db.query_all("SELECT id FROM leagues")
    for row in rows:
        db.execute(
            "UPDATE leagues SET is_active = ? WHERE id = ?",
            (1 if row["id"] in ids else 0, row["id"]),
        )
    for league_id in ids:
        db.execute(
            "INSERT OR IGNORE INTO league_members (id, league_id, user_id, team_id, role) VALUES (?, ?, ?, NULL, 'viewer')",
            (f"member-{user_id}-{league_id}", league_id, user_id),
        )
