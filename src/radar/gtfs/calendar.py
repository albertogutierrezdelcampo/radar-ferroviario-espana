"""GTFS calendar and extended-time handling."""
from __future__ import annotations

from datetime import date, datetime

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def gtfs_date(value) -> date | None:
    """Perform the documented application operation while preserving current API contracts.

    Parameters are validated or normalized by the function; relevant inputs: ``value``.
    """
    try:
        return datetime.strptime(str(value or "").strip(), "%Y%m%d").date()
    except (TypeError, ValueError):
        return None


def gtfs_seconds(value) -> int | None:
    """Perform the documented application operation while preserving current API contracts.

    Parameters are validated or normalized by the function; relevant inputs: ``value``.
    """
    try:
        hours, minutes, seconds = map(int, str(value or "").strip().split(":"))
        if hours < 0 or not 0 <= minutes < 60 or not 0 <= seconds < 60:
            return None
        return hours * 3600 + minutes * 60 + seconds
    except (TypeError, ValueError):
        return None


def active_service_ids(calendar_rows, calendar_dates_rows, on_date: date) -> set[str]:
    """Perform the documented application operation while preserving current API contracts.

    Parameters are validated or normalized by the function; relevant inputs: ``calendar_rows``, ``calendar_dates_rows``, ``on_date``.
    """
    active: set[str] = set()
    weekday = WEEKDAYS[on_date.weekday()]
    for row in calendar_rows:
        service_id = str(row.get("service_id") or "").strip()
        start, end = gtfs_date(row.get("start_date")), gtfs_date(row.get("end_date"))
        if service_id and start and end and start <= on_date <= end and str(row.get(weekday, "0")) == "1":
            active.add(service_id)
    target = on_date.strftime("%Y%m%d")
    for row in calendar_dates_rows:
        if str(row.get("date") or "").strip() != target:
            continue
        service_id = str(row.get("service_id") or "").strip()
        exception_type = str(row.get("exception_type") or "").strip()
        if exception_type == "1" and service_id:
            active.add(service_id)
        elif exception_type == "2":
            active.discard(service_id)
    return active
