#!/bin/bash
# Quality check script for Friday project
# Runs all code quality tools in sequence

set -e

echo "=== Friday Quality Checks ==="
echo ""

echo "1/4 Running Black (code formatting)..."
python -m black --check .
echo "✓ Black passed"
echo ""

echo "2/4 Running Ruff (linting)..."
python -m ruff check .
echo "✓ Ruff passed"
echo ""

echo "3/4 Running MyPy (type checking)..."
python -m mypy src tests
echo "✓ MyPy passed"
echo ""

echo "4/4 Running Pytest (tests)..."
python -m pytest
echo "✓ Pytest passed"
echo ""

echo "==================================="
echo "✓ All quality checks passed!"
echo "==================================="
