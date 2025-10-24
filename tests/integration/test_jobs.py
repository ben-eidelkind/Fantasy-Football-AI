from __future__ import annotations

import unittest

from backend import db, demo, jobs, notifications


class JobsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        db.run_migrations()
        demo.seed_demo_content()
        cls.user_id = "demo-user"
        db.execute(
            "INSERT OR IGNORE INTO users (id, email, name, is_demo) VALUES (?, ?, ?, 0)",
            (cls.user_id, "user@example.com", "User"),
        )
        db.execute(
            "INSERT OR IGNORE INTO league_members (id, league_id, user_id, role) VALUES (?, ?, ?, 'viewer')",
            (f"member-{cls.user_id}-league-001", "league-001", cls.user_id),
        )

    def test_run_all_jobs_once(self) -> None:
        jobs.run_all_jobs_once()
        notices = notifications.pending_notifications(self.user_id)
        self.assertGreaterEqual(len(notices), 1)


if __name__ == "__main__":
    unittest.main()
