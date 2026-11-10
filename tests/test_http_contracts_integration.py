"""Complete HTTP contract tests using Flask's in-process integration client."""
from __future__ import annotations

import json
import time

import pytest

pytestmark = pytest.mark.integration


def test_index_renders_shell_and_static_assets(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Radar Ferroviario" in html
    assert "/static/css/map.css" in html
    assert "/static/js/map.js" in html


def test_liveness_contract(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "service": "radar-ferroviario"}


def test_readiness_degraded_without_snapshot(client, appmod, preserve_runtime_state):
    appmod.RT_CACHE.update(trains=[], timestamp=0, last_success_at=0, last_error=None)
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.get_json()["status"] == "degraded"


def test_readiness_ready_for_recent_snapshot(client, appmod, preserve_runtime_state, monkeypatch):
    monkeypatch.setattr(appmod.time, "time", lambda: 10_000.0)
    appmod.RT_CACHE.update(trains=[{"id": "1"}], timestamp=9_950.0,
                           last_success_at=9_950.0, last_error=None)
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ready", "trains": 1, "snapshot_age_seconds": 50, "last_error": None
    }


def test_readiness_rejects_snapshot_older_than_fifteen_minutes(client, appmod, preserve_runtime_state, monkeypatch):
    monkeypatch.setattr(appmod.time, "time", lambda: 10_000.0)
    appmod.RT_CACHE.update(trains=[{"id": "1"}], last_success_at=9_099.0, last_error="old")
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.get_json()["snapshot_age_seconds"] == 901


def test_stations_fallback_contract_and_no_cache_headers(client, appmod, preserve_runtime_state):
    appmod.STATIC_CACHE.update(stations=[], stations_loaded=False)
    response = client.get("/api/stations")
    body = response.get_json()
    assert response.status_code == 200 and body["success"] is True
    assert body["count"] == len(appmod.CORE_STATIONS)
    assert body["fully_loaded"] is False
    assert "no-store" in response.headers["Cache-Control"]


def test_routes_seed_contract(client, appmod, preserve_runtime_state):
    appmod.STATIC_CACHE.update(route_polylines=[], real_tracks_loaded=False,
                               real_tracks_stage=0, real_tracks_source="seed")
    response = client.get("/api/routes")
    body = response.get_json()
    assert response.status_code == 200
    assert body["success"] is True and body["count"] == len(appmod.SEED_ROUTES)
    assert body["real_geometry_loaded"] is False


@pytest.mark.parametrize("bbox", ["", "bad", "34,-3,40,-2", "40,-3,39,-2", "40,-20,41,-19"])
def test_viewport_rejects_invalid_bounds_without_network(client, bbox):
    response = client.get("/api/routes/viewport", query_string={"bbox": bbox})
    body = response.get_json()
    assert response.status_code == 200
    assert body["success"] is True and body["added"] == 0
    assert body["overpass_error"]


def test_viewport_short_circuits_large_area(client):
    body = client.get("/api/routes/viewport?bbox=39,-4,41,-1").get_json()
    assert body == {"success": True, "added": 0, "cached": True, "note": "viewport amplio"}


def test_viewport_merges_mocked_overpass_geometry(client, appmod, preserve_runtime_state, monkeypatch):
    elements = [{"type": "way", "id": 7, "tags": {"railway": "rail"},
                 "geometry": [{"lat": 40.0, "lon": -3.0}, {"lat": 40.1, "lon": -2.9}]}]
    monkeypatch.setattr(appmod, "run_overpass_query", lambda *a, **k: (elements, None, False))
    appmod.STATIC_CACHE.update(route_polylines=[], real_tracks_loaded=False)
    body = client.get("/api/routes/viewport?bbox=39.9,-3.1,40.2,-2.8").get_json()
    assert body["success"] is True and body["added"] >= 1
    assert body["cached"] is False and body["routes"]


def test_transit_network_contract_exposes_all_sources(client, appmod, preserve_runtime_state):
    response = client.get("/api/transit-networks")
    body = response.get_json()
    assert response.status_code == 200 and body["success"] is True
    assert set(body["networks"]) == set(appmod.METRO_GTFS)
    assert body["network_summary"]["total"] == len(appmod.METRO_GTFS)
    valencia = body["networks"]["metro_valencia"]
    for field in ("status", "source_strategy", "nap_file_id", "download_attempts",
                  "using_cache", "stale", "station_count", "route_count", "trip_count"):
        assert field in valencia


def test_diagnostics_contract_and_no_store(client):
    response = client.get("/api/diagnostics")
    body = response.get_json()
    assert response.status_code == 200 and body["success"] is True
    assert response.headers["Cache-Control"] == "no-store"
    assert {"background", "counts", "feeds", "gtfs_sources", "overpass_mirrors",
            "train_snapshot", "error_log", "errors"} <= set(body)


def test_diagnostics_redacts_nested_signed_url(client, appmod, preserve_runtime_state):
    state = appmod.METRO_CACHE["metro_valencia"]
    state["download_attempts"] = [{
        "source": "https://x.s3.amazonaws.com/f.zip?X-Amz-Credential=AKIA123&X-Amz-Signature=SECRET",
        "http_status": 200,
    }]
    text = json.dumps(client.get("/api/diagnostics").get_json())
    assert "AKIA123" not in text and "SECRET" not in text and "REDACTED" in text


def test_unknown_route_is_standard_404_not_internal_error(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
