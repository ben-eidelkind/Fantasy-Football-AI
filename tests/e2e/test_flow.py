from __future__ import annotations

import json
import os
import threading
import time
import unittest
import urllib.request
from http.client import HTTPResponse

from backend import db, demo
from backend.server import AppHandler
from http.server import ThreadingHTTPServer

TEST_DB = "data/test_e2e.db"
BASE_URL = "http://127.0.0.1:8890"


class LiveServer(threading.Thread):
    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.server = ThreadingHTTPServer(("127.0.0.1", 8890), AppHandler)

    def run(self) -> None:  # pragma: no cover - server loop
        self.server.serve_forever()

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.join(timeout=1)


class EndToEndTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ["DATABASE_URL"] = TEST_DB
        db._connection_cache.clear()
        db.run_migrations()
        demo.seed_demo_content()
        cls.server = LiveServer()
        cls.server.start()
        time.sleep(0.2)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.stop()
        for conn in list(db._connection_cache.values()):
            conn.close()
        db._connection_cache.clear()
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    def _post(self, path: str, body: dict | None = None, token: str | None = None) -> dict:
        data = json.dumps(body or {}).encode()
        req = urllib.request.Request(
            BASE_URL + path,
            data=data,
            headers={
                "Content-Type": "application/json",
                **({"Authorization": f"Bearer {token}"} if token else {}),
            },
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:  # type: ignore[assignment]
            return json.loads(resp.read().decode())

    def _get(self, path: str, token: str | None = None) -> dict:
        req = urllib.request.Request(
            BASE_URL + path,
            headers={**({"Authorization": f"Bearer {token}"} if token else {})},
        )
        with urllib.request.urlopen(req) as resp:  # type: ignore[assignment]
            return json.loads(resp.read().decode())

    def test_full_onboarding_flow(self) -> None:
        code_payload = self._post("/api/auth/request-code", {"email": "test@user"})
        token_payload = self._post(
            "/api/auth/verify",
            {"email": "test@user", "code": code_payload["debug"]["code"]},
        )
        token = token_payload["token"]
        begin = self._post("/api/espn/begin", {"provider": "mock"}, token)
        self._post(
            "/api/espn/complete",
            {"state_id": begin["state_id"], "provider": "mock", "tokens": {"access_token": "mock"}},
            token,
        )
        leagues = self._post("/api/espn/sync", {"provider": "mock"}, token)
        first_league = leagues["leagues"][0]["id"]
        self._post("/api/espn/activate", {"league_ids": [first_league]}, token)
        dashboard = self._get("/api/dashboard", token)
        self.assertGreaterEqual(len(dashboard["leagues"]), 1)

    def test_demo_mode_dashboard(self) -> None:
        demo_payload = self._post("/api/demo/login", {})
        token = demo_payload["token"]
        dashboard = self._get("/api/dashboard", token)
        self.assertGreaterEqual(len(dashboard["leagues"]), 1)

    def test_league_lineup_optimizer(self) -> None:
        demo_payload = self._post("/api/demo/login", {})
        token = demo_payload["token"]
        dashboard = self._get("/api/dashboard", token)
        league_id = dashboard["leagues"][0]["league"]["id"]
        roster = self._get(f"/api/leagues/{league_id}/roster", token)
        self.assertIn("lineup", roster)
        self.assertGreaterEqual(roster["lineup"]["total_projection"], 90)

    def test_waiver_and_trade_recommendations(self) -> None:
        demo_payload = self._post("/api/demo/login", {})
        token = demo_payload["token"]
        dashboard = self._get("/api/dashboard", token)
        league_id = dashboard["leagues"][0]["league"]["id"]
        waivers = self._get(f"/api/leagues/{league_id}/waivers", token)
        trades = self._get(f"/api/leagues/{league_id}/trades", token)
        self.assertGreaterEqual(len(waivers["candidates"]), 1)
        self.assertGreaterEqual(len(trades["proposals"]), 1)


if __name__ == "__main__":
    unittest.main()
