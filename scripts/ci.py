"""CI entry point that supports stage-specific commands."""
from __future__ import annotations

import argparse
import compileall
import sys
import unittest

from backend import db, demo


def run_lint() -> None:
    if not compileall.compile_dir("backend", quiet=1):
        raise SystemExit(1)


def run_types() -> None:
    if not compileall.compile_dir("tests", quiet=1):
        raise SystemExit(1)


def run_unit() -> None:
    from tests.unit import test_analysis

    suite = unittest.TestLoader().loadTestsFromModule(test_analysis)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)


def run_integration() -> None:
    from tests.integration import test_espn_mock, test_jobs

    loader = unittest.TestLoader()
    suite = unittest.TestSuite(
        [
            loader.loadTestsFromModule(test_espn_mock),
            loader.loadTestsFromModule(test_jobs),
        ]
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)


def run_e2e() -> None:
    from tests.e2e import test_flow

    suite = unittest.TestLoader().loadTestsFromModule(test_flow)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)


def run_build() -> None:
    db.run_migrations()
    demo.seed_demo_content()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["lint", "types", "unit", "integration", "e2e", "build"])
    args = parser.parse_args()
    stages = {
        "lint": run_lint,
        "types": run_types,
        "unit": run_unit,
        "integration": run_integration,
        "e2e": run_e2e,
        "build": run_build,
    }
    stages[args.stage]()


if __name__ == "__main__":
    main()
