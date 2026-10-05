"""Shared test configuration."""

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
GOLDEN_DIR = PROJECT_ROOT / "tests" / "golden"
SNAPSHOTS_DIR = PROJECT_ROOT / "tests" / "snapshots"


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    if not FIXTURES_DIR.exists() or not any(FIXTURES_DIR.glob("*.pdf")):
        pytest.fail("fixture corpus missing; run: python scripts/make_fixtures.py")
    return FIXTURES_DIR


@pytest.fixture(scope="session")
def golden_dir() -> Path:
    if not GOLDEN_DIR.exists() or not any(GOLDEN_DIR.glob("*.golden.json")):
        pytest.fail("golden files missing; run: python scripts/update_golden.py")
    return GOLDEN_DIR
