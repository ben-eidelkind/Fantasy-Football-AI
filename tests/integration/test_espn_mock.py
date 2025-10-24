from __future__ import annotations

import unittest

from backend import db, demo, espn


class ESPNMockTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        db.run_migrations()
        demo.seed_demo_content()
        cls.user_id = "test-user"
        db.execute(
            "INSERT OR IGNORE INTO users (id, email, name, is_demo) VALUES (?, ?, ?, 0)",
            (cls.user_id, "test@example.com", "Test",),
        )

    def test_begin_and_complete_flow(self) -> None:
        state = espn.begin_connection(self.user_id, provider_name="mock")
        self.assertTrue(state.authorization_url.startswith("/mock-espn"))
        tokens = espn.complete_connection(state.state_id, {"access_token": "mock"}, provider_name="mock")
        self.assertIn("access_token", tokens)

    def test_sync_leagues(self) -> None:
        state = espn.begin_connection(self.user_id, provider_name="mock")
        espn.complete_connection(state.state_id, {"access_token": "mock"}, provider_name="mock")
        leagues = espn.sync_leagues(self.user_id, provider_name="mock")
        self.assertGreaterEqual(len(leagues), 1)
        active = espn.active_leagues_for_user(self.user_id)
        self.assertEqual(active, [])  # not activated yet
        espn.set_active_leagues(self.user_id, [leagues[0]["id"]])
        active = espn.active_leagues_for_user(self.user_id)
        self.assertEqual(len(active), 1)


if __name__ == "__main__":
    unittest.main()
