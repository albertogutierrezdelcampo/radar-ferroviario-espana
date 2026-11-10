import io
import zipfile

import pytest

from radar.gtfs import GtfsValidationError, open_gtfs_archive


def make_gtfs(*, nested=False, include_calendar=True, omit=()):
    files = {
        "stops.txt": "stop_id,stop_name,stop_lat,stop_lon\nS1,Estación,40.4,-3.7\n",
        "routes.txt": "route_id,route_short_name\nR1,C1\n",
        "trips.txt": "route_id,service_id,trip_id\nR1,WK,T1\n",
        "stop_times.txt": "trip_id,arrival_time,departure_time,stop_id,stop_sequence\nT1,25:00:00,25:01:00,S1,1\n",
    }
    if include_calendar:
        files["calendar.txt"] = "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\nWK,1,1,1,1,1,0,0,20260101,20261231\n"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        for name, content in files.items():
            if name not in omit:
                archive.writestr(f"feed/sub/{name}" if nested else name, content)
    return buf.getvalue()


def test_reads_required_tables_inside_nested_directories():
    archive = open_gtfs_archive(make_gtfs(nested=True))
    assert archive.table("stops.txt")[0]["stop_name"] == "Estación"
    assert archive.files["routes.txt"] == "feed/sub/routes.txt"
    assert archive.summary()["row_counts"]["stop_times.txt"] == 1


def test_utf8_bom_is_supported():
    source = make_gtfs()
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(source)) as original, zipfile.ZipFile(output, "w") as rebuilt:
        for member in original.namelist():
            content = original.read(member)
            if member.endswith("stops.txt"):
                content = b"\xef\xbb\xbf" + content
            rebuilt.writestr(member, content)
    assert open_gtfs_archive(output.getvalue()).table("stops.txt")[0]["stop_id"] == "S1"


def test_missing_required_table_is_rejected():
    with pytest.raises(GtfsValidationError, match="stop_times.txt"):
        open_gtfs_archive(make_gtfs(omit=("stop_times.txt",)))


def test_non_zip_and_corrupt_zip_are_rejected():
    with pytest.raises(GtfsValidationError, match="firma ZIP"):
        open_gtfs_archive(b"not-a-zip")
    with pytest.raises(GtfsValidationError):
        open_gtfs_archive(b"PKbroken")


def test_missing_calendar_is_warning_not_error():
    archive = open_gtfs_archive(make_gtfs(include_calendar=False))
    assert archive.table("calendar.txt") == []
    assert len(archive.warnings) == 2
