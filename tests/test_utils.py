from datetime import datetime

from radar.utils import (
    _bearing_degrees, _gtfs_date, _gtfs_seconds, _shift_gtfs_time,
    extract_train_number, haversine_km, parse_float, simplify_track_geometry,
    smooth_chaikin, train_number_aliases,
)


def test_parse_float_accepts_comma_and_numbers():
    assert parse_float("41,6425") == 41.6425
    assert parse_float(12) == 12.0
    assert parse_float("no-num") is None


def test_geographic_helpers():
    assert 170 < haversine_km(40.4168, -3.7038, 41.3874, 2.1686) < 520
    assert 80 <= _bearing_degrees(40.0, -4.0, 40.0, -3.0) <= 100


def test_train_number_helpers():
    assert extract_train_number("AVE 01803 Madrid") == "01803"
    assert "01803" in train_number_aliases("AVE 01803 Madrid")
    assert "1803" in train_number_aliases("AVE 01803 Madrid")


def test_gtfs_time_helpers():
    assert _gtfs_seconds("25:10:05") == 90605
    assert _shift_gtfs_time("10:00:00", 90) == "10:01:30"
    assert _gtfs_date("20261110") == datetime(2026, 11, 10).date()


def test_geometry_helpers_do_not_mutate_shape_contract():
    coords = [[0.0, 0.0], [1.0, 1.0], [2.0, 0.0]]
    assert smooth_chaikin(coords, iterations=1)[0] == coords[0]
    assert smooth_chaikin(coords, iterations=1)[-1] == coords[-1]
    assert simplify_track_geometry(coords)[0] == coords[0]
