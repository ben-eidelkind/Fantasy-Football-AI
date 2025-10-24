"""Run unit, integration, and e2e suites with deterministic ordering."""
from __future__ import annotations

import os
import sys
import unittest

TEST_MODULES = [
    "tests.unit.test_analysis",
    "tests.integration.test_espn_mock",
    "tests.integration.test_jobs",
    "tests.e2e.test_flow",
]


def main() -> None:
    loader = unittest.TestLoader()
    suites = [loader.loadTestsFromName(name) for name in TEST_MODULES]
    suite = unittest.TestSuite(suites)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)


if __name__ == "__main__":
    main()
