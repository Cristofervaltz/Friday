#!/usr/bin/env bash
set -euo pipefail

python -m black --check .
python -m ruff check .
python -m mypy src tests
python -m pytest
