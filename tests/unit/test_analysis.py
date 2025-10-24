from __future__ import annotations

import unittest

from backend import analysis, db, demo


class AnalysisTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        db.run_migrations()
        demo.seed_demo_content()

    def test_blend_projections(self) -> None:
        projection = analysis.blend_projections("player-001", week=8)
        self.assertGreater(projection.projected_points, 0)
        self.assertAlmostEqual(projection.floor, 17.83, places=2)

    def test_start_sit_delta_positive(self) -> None:
        lineup = analysis.start_sit_for_roster("roster-001")
        self.assertIsNotNone(lineup)
        self.assertGreaterEqual(lineup.total_projection, 90)
        self.assertGreaterEqual(len(lineup.lineup), 1)

    def test_trade_ideas_increase_lineup(self) -> None:
        proposals = analysis.trade_ideas("league-001", "team-001")
        self.assertTrue(all(proposal.lineup_delta > 0 for proposal in proposals))

    def test_simulation_reproducible(self) -> None:
        first = analysis.simulate_matchup("league-001", "team-001", "team-002", runs=50)
        second = analysis.simulate_matchup("league-001", "team-001", "team-002", runs=50)
        self.assertAlmostEqual(first.win_probability, second.win_probability)


if __name__ == "__main__":
    unittest.main()
