from pathlib import Path


def test_metro_loader_delegates_acquisition_to_nap_service():
    source = Path(__file__).resolve().parents[1].joinpath("src", "radar_app", "application.py").read_text(encoding="utf-8")
    function = source[source.index("def load_metro_gtfs"):source.index("def ensure_metro_feeds")]
    assert "NAP_GTFS_SERVICE.acquire(" in function
    assert "download_attempts=fetch.attempts" in function
    assert 'status="stale" if fetch.stale' in function
