"""Compatibility entry point for Flask, Gunicorn and existing tests.

The implementation lives under ``src/radar_app/application.py``.  It is
executed in this module namespace deliberately: legacy code and tests that
patch symbols such as ``fetch_json_entities`` keep working while the remaining
monolith is extracted incrementally into services and blueprints.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

_IMPLEMENTATION = SRC_DIR / "radar_app" / "application.py"
exec(compile(_IMPLEMENTATION.read_bytes(), str(_IMPLEMENTATION), "exec"), globals(), globals())
