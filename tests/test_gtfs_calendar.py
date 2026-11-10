from datetime import date

from radar.gtfs.calendar import active_service_ids, gtfs_date, gtfs_seconds


def test_gtfs_extended_times_and_invalid_values():
    assert gtfs_seconds("25:10:05") == 90605
    assert gtfs_seconds("10:60:00") is None
    assert gtfs_seconds("bad") is None
    assert gtfs_date("20261110") == date(2026, 11, 10)
    assert gtfs_date("20261399") is None


def test_weekly_calendar_with_add_remove_exceptions():
    rows = [{
        "service_id": "weekday", "monday": "1", "tuesday": "1", "wednesday": "1",
        "thursday": "1", "friday": "1", "saturday": "0", "sunday": "0",
        "start_date": "20260101", "end_date": "20261231",
    }]
    exceptions = [
        {"service_id": "weekday", "date": "20261110", "exception_type": "2"},
        {"service_id": "special", "date": "20261110", "exception_type": "1"},
    ]
    assert active_service_ids(rows, exceptions, date(2026, 11, 10)) == {"special"}


def test_calendar_dates_only_feed_is_supported():
    assert active_service_ids([], [{
        "service_id": "event", "date": "20261110", "exception_type": "1"
    }], date(2026, 11, 10)) == {"event"}
