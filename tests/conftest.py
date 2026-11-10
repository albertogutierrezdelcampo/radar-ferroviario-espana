"""Pytest bootstrap for local runs and CI.

Ensures the repository root is importable even when pytest is launched through
the console entry point or with importlib-based import mode.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
