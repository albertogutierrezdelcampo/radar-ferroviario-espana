"""Regression test for module-level dependency initialization order."""
from pathlib import Path


def test_overpass_http_exists_before_service_is_constructed():
    source = Path(__file__).resolve().parents[1].joinpath("src", "radar_app", "application.py").read_text(encoding="utf-8")
    http_init = source.index("OVERPASS_HTTP = requests.Session()")
    service_init = source.index("OVERPASS_SERVICE = OverpassService(")
    assert http_init < service_init
