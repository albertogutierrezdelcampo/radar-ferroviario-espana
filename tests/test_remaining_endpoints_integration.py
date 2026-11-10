"""Integration coverage for alerts, operators and ADIF cache-only behavior."""
from __future__ import annotations

import time

import pytest

pytestmark = pytest.mark.integration


def test_alerts_returns_fresh_cached_snapshot_without_network(client, appmod, preserve_runtime_state, monkeypatch):
    now = 50_000.0
    monkeypatch.setattr(appmod.time, "time", lambda: now)
    cached = [{"id": "A1", "title": "Incidencia", "severity": "MEDIA"}]
    appmod.ALERTS_CACHE.update(timestamp=now - 10, alerts=cached, diagnostics={"source": "test"})
    response = client.get("/api/alerts")
    body = response.get_json()
    assert response.status_code == 200
    assert body["success"] is True
    assert body["count"] == 1 and body["alerts"] == cached
    assert body["diagnostics"] == {"source": "test"}


def test_operators_endpoint_exposes_configured_catalog(client, appmod, preserve_runtime_state):
    response = client.get("/api/operators")
    body = response.get_json()
    assert response.status_code == 200 and body["success"] is True
    assert set(body["operators"]) == set(appmod.OPEN_ACCESS_GTFS)
    for key, operator in body["operators"].items():
        assert operator["key"] == key
        assert {"loaded", "loading", "error", "source"} <= set(operator)


def test_adif_catalog_uses_fresh_cache_without_network(client, appmod, preserve_runtime_state, monkeypatch):
    now = 60_000.0
    monkeypatch.setattr(appmod.time, "time", lambda: now)
    datasets = [{"title": "Estaciones", "url": "https://example.test/data.geojson"}]
    appmod.ADIF_CACHE.update(timestamp=now - 5, datasets=datasets)
    body = client.get("/api/adif/catalog").get_json()
    assert body == {"success": True, "datasets": datasets}


def test_adif_layer_requires_url(client):
    body = client.get("/api/adif/layer").get_json()
    assert body["success"] is False
    assert "url" in body["error"]


def test_adif_layer_uses_cached_geojson_without_network(client, appmod, preserve_runtime_state):
    url = "https://services.arcgis.com/example/FeatureServer/0"
    geojson = {"type": "FeatureCollection", "features": []}
    appmod.ADIF_CACHE["layers_geojson"][url] = geojson
    body = client.get("/api/adif/layer", query_string={"url": url}).get_json()
    assert body == {"success": True, "geojson": geojson}


def test_diagnostics_log_download_creates_empty_file(client, appmod, monkeypatch, tmp_path):
    log = tmp_path / "missing.log"
    monkeypatch.setitem(appmod.download_error_log.__globals__, "ERROR_LOG_FILE", str(log))
    response = client.get("/api/diagnostics/log")
    assert response.status_code == 200
    assert response.mimetype == "text/plain"
    assert log.exists()
