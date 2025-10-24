"""Minimal HTTP server powering the Fantasy Football AI application."""
from __future__ import annotations

import json
import logging
import mimetypes
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import analysis, auth, db, demo, espn, feature_flags, jobs, notifications
from .config import get_settings

LOGGER = logging.getLogger(__name__)
STATIC_ROOT = Path(__file__).resolve().parents[1] / "public"


def _json_response(handler: BaseHTTPRequestHandler, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _bad_request(handler: BaseHTTPRequestHandler, message: str) -> None:
    _json_response(handler, {"error": message}, HTTPStatus.BAD_REQUEST)


def _parse_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if length == 0:
        return {}
    data = handler.rfile.read(length)
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return {}


def _get_session(handler: BaseHTTPRequestHandler) -> dict | None:
    token = handler.headers.get("Authorization")
    if not token:
        return None
    if token.startswith("Bearer "):
        token = token.split(" ", 1)[1]
    return auth.get_user_by_session(token)


class AppHandler(BaseHTTPRequestHandler):
    server_version = "FantasyFootballAI/1.0"

    def log_message(self, format: str, *args) -> None:  # pragma: no cover - request log
        LOGGER.info("%s - %s", self.address_string(), format % args)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/api/"):
            self.handle_api_get()
        else:
            self.serve_static()

    def do_POST(self) -> None:  # noqa: N802
        if not self.path.startswith("/api/"):
            _bad_request(self, "POST not allowed")
            return
        self.handle_api_post()

    # API routing ---------------------------------------------------------
    def handle_api_get(self) -> None:
        user = _get_session(self)
        parsed = urlparse(self.path)
        if parsed.path == "/api/me":
            if not user:
                _json_response(self, {"authenticated": False})
                return
            flags = feature_flags.get_flags_for_user(user["id"])
            _json_response(
                self,
                {"authenticated": True, "user": user, "feature_flags": flags},
            )
            return
        if not user:
            _bad_request(self, "Authentication required")
            return
        if parsed.path == "/api/dashboard":
            payload = build_dashboard_payload(user["id"])
            _json_response(self, payload)
            return
        if parsed.path.startswith("/api/leagues/") and parsed.path.endswith("/roster"):
            league_id = parsed.path.split("/")[3]
            roster = get_league_roster_payload(league_id, user["id"])
            _json_response(self, roster)
            return
        if parsed.path.startswith("/api/leagues/") and parsed.path.endswith("/waivers"):
            league_id = parsed.path.split("/")[3]
            waivers = get_waiver_payload(league_id, user["id"])
            _json_response(self, waivers)
            return
        if parsed.path.startswith("/api/leagues/") and parsed.path.endswith("/trades"):
            league_id = parsed.path.split("/")[3]
            trades = get_trade_payload(league_id, user["id"])
            _json_response(self, trades)
            return
        if parsed.path.startswith("/api/leagues/") and parsed.path.endswith("/matchup"):
            league_id = parsed.path.split("/")[3]
            query = parse_qs(parsed.query)
            opponent = query.get("opponent", [None])[0]
            matchup = get_matchup_payload(league_id, user["id"], opponent)
            _json_response(self, matchup)
            return
        if parsed.path == "/api/notifications":
            notices = notifications.pending_notifications(user["id"])
            _json_response(self, {"notifications": notices})
            return
        _bad_request(self, "Unknown endpoint")

    def handle_api_post(self) -> None:
        parsed = urlparse(self.path)
        body = _parse_body(self)
        if parsed.path == "/api/auth/request-code":
            email = body.get("email")
            if not email:
                _bad_request(self, "email required")
                return
            payload = auth.request_login_code(email)
            _json_response(self, {"status": "sent", "debug": payload})
            return
        if parsed.path == "/api/auth/verify":
            email = body.get("email")
            code = body.get("code")
            if not email or not code:
                _bad_request(self, "email and code required")
                return
            result = auth.verify_login_code(email, code)
            if not result:
                _bad_request(self, "invalid code")
                return
            _json_response(self, {"token": result["session"]["token"], "user_id": result["user_id"]})
            return
        if parsed.path == "/api/demo/login":
            result = auth.create_demo_user()
            demo.seed_demo_content()
            _json_response(self, {"token": result["session"]["token"], "user_id": result["user_id"]})
            return
        user = _get_session(self)
        if not user:
            _bad_request(self, "Authentication required")
            return
        if parsed.path == "/api/auth/logout":
            token = self.headers.get("Authorization", "").replace("Bearer ", "")
            auth.revoke_session(token)
            _json_response(self, {"status": "signed-out"})
            return
        if parsed.path == "/api/espn/begin":
            provider = body.get("provider", "mock")
            state = espn.begin_connection(user["id"], provider)
            _json_response(self, {"state_id": state.state_id, "authorization_url": state.authorization_url})
            return
        if parsed.path == "/api/espn/complete":
            provider = body.get("provider", "mock")
            state_id = body.get("state_id")
            tokens = body.get("tokens", {})
            result = espn.complete_connection(state_id, tokens, provider)
            _json_response(self, {"connected": True, "tokens": result})
            return
        if parsed.path == "/api/espn/sync":
            provider = body.get("provider", "mock")
            leagues = espn.sync_leagues(user["id"], provider)
            _json_response(self, {"leagues": leagues})
            return
        if parsed.path == "/api/espn/activate":
            league_ids = body.get("league_ids", [])
            espn.set_active_leagues(user["id"], league_ids)
            _json_response(self, {"status": "updated"})
            return
        if parsed.path == "/api/feature-flags":
            flag = body.get("flag")
            enabled = bool(body.get("enabled", True))
            if not flag:
                _bad_request(self, "flag required")
                return
            feature_flags.set_flag(user["id"], flag, enabled)
            _json_response(self, {"status": "ok"})
            return
        _bad_request(self, "Unknown endpoint")

    # Static file handling ------------------------------------------------
    def serve_static(self) -> None:
        parsed = urlparse(self.path)
        path = STATIC_ROOT / parsed.path.lstrip("/")
        if path.is_dir():
            path = path / "index.html"
        if not path.exists():
            path = STATIC_ROOT / "index.html"
        content = path.read_bytes()
        mimetype, _ = mimetypes.guess_type(str(path))
        self.send_response(HTTPStatus.OK)
        if mimetype:
            self.send_header("Content-Type", mimetype)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def build_dashboard_payload(user_id: str) -> dict:
    leagues = espn.active_leagues_for_user(user_id)
    cards = []
    for league in leagues:
        team_row = db.query_one(
            "SELECT teams.id as team_id, teams.playoff_odds FROM teams JOIN league_members ON league_members.team_id = teams.id WHERE league_members.user_id = ? AND teams.league_id = ?",
            (user_id, league["id"]),
        )
        team_id = team_row["team_id"] if team_row else None
        waivers = []
        matchup = None
        lineup = None
        if team_id:
            waivers = [asdict(c) for c in analysis.waiver_recommendations(league["id"], team_id)]
            opponent = db.query_one(
                "SELECT away_team_id FROM matchups WHERE home_team_id = ? LIMIT 1",
                (team_id,),
            )
            if opponent:
                matchup_result = analysis.simulate_matchup(league["id"], team_id, opponent["away_team_id"], runs=120)
                matchup = asdict(matchup_result)
            roster_row = db.query_one(
                "SELECT id FROM rosters WHERE league_id = ? AND team_id = ? ORDER BY week DESC LIMIT 1",
                (league["id"], team_id),
            )
            if roster_row:
                lineup = asdict(analysis.start_sit_for_roster(roster_row["id"]))
        cards.append(
            {
                "league": league,
                "team_id": team_id,
                "matchup": matchup,
                "waivers": waivers,
                "lineup": lineup,
            }
        )
    return {"leagues": cards}


def get_league_roster_payload(league_id: str, user_id: str) -> dict:
    team = db.query_one(
        "SELECT team_id FROM league_members WHERE user_id = ? AND league_id = ? ORDER BY role DESC LIMIT 1",
        (user_id, league_id),
    )
    if not team:
        raise ValueError("team not found")
    roster = db.query_one(
        "SELECT id FROM rosters WHERE league_id = ? AND team_id = ? ORDER BY week DESC LIMIT 1",
        (league_id, team["team_id"]),
    )
    lineup = analysis.start_sit_for_roster(roster["id"]) if roster else None
    return {
        "team_id": team["team_id"],
        "lineup": asdict(lineup) if lineup else None,
    }


def get_waiver_payload(league_id: str, user_id: str) -> dict:
    team = db.query_one(
        "SELECT team_id FROM league_members WHERE user_id = ? AND league_id = ? ORDER BY role DESC LIMIT 1",
        (user_id, league_id),
    )
    if not team:
        raise ValueError("team not found")
    candidates = [asdict(c) for c in analysis.waiver_recommendations(league_id, team["team_id"])]
    return {"candidates": candidates}


def get_trade_payload(league_id: str, user_id: str) -> dict:
    team = db.query_one(
        "SELECT team_id FROM league_members WHERE user_id = ? AND league_id = ? ORDER BY role DESC LIMIT 1",
        (user_id, league_id),
    )
    if not team:
        raise ValueError("team not found")
    proposals = [
        {
            "offer_players": [asdict(player) for player in proposal.offer_players],
            "request_players": [asdict(player) for player in proposal.request_players],
            "offer_value": proposal.offer_value,
            "request_value": proposal.request_value,
            "lineup_delta": proposal.lineup_delta,
            "playoff_odds_delta": proposal.playoff_odds_delta,
            "notes": proposal.notes,
        }
        for proposal in analysis.trade_ideas(league_id, team["team_id"])
    ]
    return {"proposals": proposals}


def get_matchup_payload(league_id: str, user_id: str, opponent_team_id: str | None) -> dict:
    team = db.query_one(
        "SELECT team_id FROM league_members WHERE user_id = ? AND league_id = ? ORDER BY role DESC LIMIT 1",
        (user_id, league_id),
    )
    if not team:
        raise ValueError("team not found")
    if not opponent_team_id:
        matchup = db.query_one(
            "SELECT away_team_id FROM matchups WHERE home_team_id = ? LIMIT 1",
            (team["team_id"],),
        )
        opponent_team_id = matchup["away_team_id"] if matchup else None
    if not opponent_team_id:
        return {"error": "No opponent"}
    result = analysis.simulate_matchup(league_id, team["team_id"], opponent_team_id, runs=200)
    return asdict(result)


def run(host: str = "0.0.0.0", port: int = 8787) -> None:
    settings = get_settings()
    db.run_migrations()
    if settings.demo_mode_enabled:
        demo.seed_demo_content()
    jobs.start_scheduler()
    server = ThreadingHTTPServer((host, port), AppHandler)
    LOGGER.info("Server listening on %s:%s", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover - manual stop
        LOGGER.info("Shutting down")
    finally:
        jobs.stop_scheduler()
        server.server_close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
