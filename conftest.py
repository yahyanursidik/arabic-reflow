"""Pytest bootstrap: make the repository root importable (apps.api etc.)."""

import sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parent)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
