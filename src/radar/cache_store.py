"""Small atomic JSON persistence helpers for disk-backed caches."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def read_json(path: str | Path, default: Any) -> Any:
    """Perform the documented application operation while preserving current API contracts.

    Parameters are validated or normalized by the function; relevant inputs: ``path``, ``default``.
    """
    target = Path(path)
    try:
        with target.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def write_json_atomic(path: str | Path, payload: Any) -> None:
    """Perform the documented application operation while preserving current API contracts.

    Parameters are validated or normalized by the function; relevant inputs: ``path``, ``payload``.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)
