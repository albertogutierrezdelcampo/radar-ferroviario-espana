"""Safe GTFS ZIP discovery, validation and CSV reading."""
from __future__ import annotations

import csv
import io
import zipfile
from pathlib import PurePosixPath

from radar.gtfs.models import GtfsArchive, GtfsValidationError

REQUIRED_FILES = ("stops.txt", "routes.txt", "trips.txt", "stop_times.txt")
OPTIONAL_FILES = ("calendar.txt", "calendar_dates.txt", "shapes.txt", "frequencies.txt", "agency.txt", "feed_info.txt")


def _canonical(name: str) -> str:
    """Perform the documented application operation while preserving current API contracts.

    Parameters are validated or normalized by the function; relevant inputs: ``name``.
    """
    return PurePosixPath(name.replace("\\", "/")).name.lower()


def discover_gtfs_files(zf: zipfile.ZipFile) -> dict[str, str]:
    """Perform the documented application operation while preserving current API contracts.

    Parameters are validated or normalized by the function; relevant inputs: ``zf``.
    """
    found: dict[str, str] = {}
    for member in zf.namelist():
        canonical = _canonical(member)
        if canonical and canonical not in found and not member.endswith("/"):
            found[canonical] = member
    return found


def validate_gtfs_archive(zf: zipfile.ZipFile) -> dict[str, str]:
    """Perform the documented application operation while preserving current API contracts.

    Parameters are validated or normalized by the function; relevant inputs: ``zf``.
    """
    files = discover_gtfs_files(zf)
    missing = [name for name in REQUIRED_FILES if name not in files]
    if missing:
        raise GtfsValidationError("GTFS incompleto; faltan: " + ", ".join(missing))
    corrupt = zf.testzip()
    if corrupt:
        raise GtfsValidationError(f"ZIP GTFS corrupto en {corrupt}")
    return files


def read_gtfs_csv(zf: zipfile.ZipFile, files: dict[str, str], name: str, *, required=False):
    """Perform the documented application operation while preserving current API contracts.

    Parameters are validated or normalized by the function; relevant inputs: ``zf``, ``files``, ``name``.
    """
    canonical = name.lower()
    member = files.get(canonical)
    if not member:
        if required:
            raise GtfsValidationError(f"Falta {canonical}")
        return []
    try:
        with zf.open(member) as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace", newline="")
            return [dict(row) for row in csv.DictReader(text)]
    except (OSError, csv.Error, UnicodeError) as exc:
        raise GtfsValidationError(f"No se pudo leer {canonical}: {exc}") from exc


def open_gtfs_archive(content: bytes, *, include: tuple[str, ...] | None = None) -> GtfsArchive:
    """Perform the documented application operation while preserving current API contracts.

    Parameters are validated or normalized by the function; relevant inputs: ``content``.
    """
    if not isinstance(content, (bytes, bytearray)) or not bytes(content).startswith(b"PK"):
        raise GtfsValidationError("El contenido no tiene firma ZIP")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            files = validate_gtfs_archive(zf)
            selected = include or REQUIRED_FILES + OPTIONAL_FILES
            rows = {name: read_gtfs_csv(zf, files, name, required=name in REQUIRED_FILES)
                    for name in selected if name in files or name in REQUIRED_FILES}
            warnings = [f"No se encontró {name}" for name in ("calendar.txt", "calendar_dates.txt")
                        if name not in files]
            return GtfsArchive(files=files, rows=rows, warnings=warnings)
    except zipfile.BadZipFile as exc:
        raise GtfsValidationError("ZIP GTFS inválido") from exc
