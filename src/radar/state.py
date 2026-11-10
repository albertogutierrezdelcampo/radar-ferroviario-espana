"""Thread-safe in-memory application state.

The module owns cache construction and locks. Services keep using the legacy
mapping names through aliases in app.py during the incremental migration.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


def _metro_state(config: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Perform the documented application operation while preserving current API contracts.

    Parameters are validated or normalized by the function; relevant inputs: ``config``.
    """
    return {
        key: {
            "loaded": False, "loading": False, "updated_at": 0,
            "last_checked": 0, "next_refresh": 0, "error": None,
            "status": "pending", "active_source": None, "using_cache": False, "stale": False,
            "cache_age_seconds": None, "download_attempts": [], "last_attempt_at": 0,
            "last_success_at": 0, "retry_after": 0.0, "attempt_id": 0, "stations": [], "routes": [],
            "trips": [], "name": cfg["name"], "color": cfg["color"],
            "source": cfg["source"],
        }
        for key, cfg in config.items()
    }


def _operator_state(config: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Perform the documented application operation while preserving current API contracts.

    Parameters are validated or normalized by the function; relevant inputs: ``config``.
    """
    return {
        key: {
            "loaded": False, "loading": False, "updated_at": 0, "error": None,
            "stations": [], "routes": [], "trips": [], "name": cfg["name"],
            "color": cfg["color"], "source": cfg["source"],
        }
        for key, cfg in config.items()
    }


def _static_cache() -> dict[str, Any]:
    """Perform the documented application operation while preserving current API contracts.
    """
    return {
        "stations_loaded": False, "stations_loading": False,
        "real_tracks_loaded": False, "real_tracks_loading": False,
        "real_tracks_stage": 0,
        "real_tracks_source": "Preparando red ferroviaria de España en segundo plano…",
        "real_tracks_started_at": 0, "real_tracks_last_progress_at": 0,
        "real_tracks_last_completed_at": 0, "real_tracks_error": None,
        "real_tracks_stages_completed": [], "real_tracks_stages_failed": [],
        "stations": [], "stops_by_id": {}, "routes_by_id": {}, "trips_by_id": {},
        "trips_by_num": {}, "trip_stops_by_id": {}, "trip_stops_by_num": {},
        "route_polylines": [], "osm_ways_seen": set(),
        "viewport_bboxes_loaded": [], "track_segment_grid": {},
    }


@dataclass(slots=True)
class ApplicationState:
    started_at: float
    metro_cache: dict[str, Any]
    open_access_cache: dict[str, Any]
    overpass_query_cache: dict[str, Any]
    overpass_endpoint_health: dict[str, Any]
    overpass_inflight: dict[str, Any] = field(default_factory=dict)
    train_motion_history: dict[str, Any] = field(default_factory=dict)
    static_cache: dict[str, Any] = field(default_factory=_static_cache)
    realtime_cache: dict[str, Any] = field(default_factory=lambda: {
        "timestamp": 0, "trains": [], "diagnostics": {}, "last_success_at": 0,
        "last_attempt_at": 0, "last_error": None, "discarded_vehicles": 0,
    })
    alerts_cache: dict[str, Any] = field(default_factory=lambda: {
        "timestamp": 0, "alerts": [], "diagnostics": {},
    })
    adif_cache: dict[str, Any] = field(default_factory=lambda: {
        "timestamp": 0, "datasets": [], "layers_geojson": {},
    })
    metro_lock: threading.RLock = field(default_factory=threading.RLock)
    open_access_lock: threading.RLock = field(default_factory=threading.RLock)
    overpass_lock: threading.RLock = field(default_factory=threading.RLock)
    train_refresh_lock: threading.Lock = field(default_factory=threading.Lock)


def create_application_state(metro_config: dict[str, Any], operator_config: dict[str, Any],
                             overpass_endpoints: list[str]) -> ApplicationState:
    """Perform the documented application operation while preserving current API contracts.

    Parameters are validated or normalized by the function; relevant inputs: ``metro_config``, ``operator_config``, ``overpass_endpoints``.
    """
    return ApplicationState(
        started_at=time.time(),
        metro_cache=_metro_state(metro_config),
        open_access_cache=_operator_state(operator_config),
        overpass_query_cache={},
        overpass_endpoint_health={
            url: {"fails": 0, "retry_after": 0.0} for url in overpass_endpoints
        },
    )
