from pathlib import Path

from radar.config import METRO_GTFS


def test_current_valencia_and_mallorca_source_configuration():
    valencia = METRO_GTFS["metro_valencia"]
    mallorca = METRO_GTFS["mallorca_rail"]
    assert valencia["nap_id"] == 1168
    assert valencia["source_strategy"] == "nap_file_id"
    assert 967 not in [valencia["nap_id"]]
    assert mallorca["nap_id"] is None
    assert mallorca["source_strategy"] == "official_direct"
    assert any("tib.org" in url and url.endswith("3d94d08e-b214-62d2-7b8c-ef3bebb9a8c0")
               for url in mallorca["fallback_urls"])


def test_transit_and_diagnostics_expose_download_cache_fields():
    source = Path(__file__).resolve().parents[1].joinpath(
        "src", "radar_app", "application.py"
    ).read_text(encoding="utf-8")
    helper = source[source.index("def _transit_source_diagnostics"):source.index("def api_transit_networks")]
    for field in (
        "source_page", "source_strategy", "nap_file_id", "fallback_urls",
        "stale", "cache_age_seconds", "download_attempts", "last_attempt_at",
        "last_success_at", "active_source", "using_cache", "error",
    ):
        assert f'"{field}"' in helper
    assert '"gtfs_sources"' in source[source.index("def api_diagnostics"):]
