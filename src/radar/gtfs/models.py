"""Typed results and errors for GTFS static archives."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class GtfsValidationError(ValueError):
    """Raised when a ZIP is not a usable GTFS static feed."""


@dataclass(slots=True)
class GtfsArchive:
    files: dict[str, str]
    rows: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def table(self, name: str) -> list[dict[str, str]]:
        """Perform the documented application operation while preserving current API contracts.

        Parameters are validated or normalized by the function; relevant inputs: ``name``.
        """
        return self.rows.get(name.lower(), [])

    def summary(self) -> dict[str, Any]:
        """Perform the documented application operation while preserving current API contracts.
        """
        return {"files": dict(self.files), "row_counts": {k: len(v) for k, v in self.rows.items()},
                "warnings": list(self.warnings)}
