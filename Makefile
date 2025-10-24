.PHONY: setup serve test changelog

setup:
python -m scripts.setup

serve:
python -m backend.server

test:
python -m tests.run_all

changelog:
python tools/generate_changelog.py
