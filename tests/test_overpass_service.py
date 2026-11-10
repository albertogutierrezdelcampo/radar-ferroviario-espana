import logging
import threading
import time

import requests

from radar.overpass_service import OverpassService


class Response:
    status_code = 200
    def json(self): return {"elements": [{"type": "way", "id": 1}]}


class RotatingHttp:
    def __init__(self): self.calls = []
    def post(self, endpoint, **kwargs):
        self.calls.append((endpoint, kwargs["timeout"]))
        if endpoint.endswith("slow"):
            raise requests.exceptions.ReadTimeout("slow")
        return Response()


def service(tmp_path, http, cache=None):
    endpoints = ["https://mirror/slow", "https://mirror/fast"]
    return OverpassService(
        endpoints=endpoints, cache=cache if cache is not None else {},
        health={url: {"fails": 0, "retry_after": 0.0} for url in endpoints},
        inflight={}, lock=threading.RLock(), http=http,
        cache_file=tmp_path / "overpass.json", cache_ttl=10,
        failure_cooldown=180, logger=logging.getLogger("test.overpass"),
    )


def test_rotates_after_one_attempt_and_uses_bounded_timeout(tmp_path):
    http = RotatingHttp(); svc = service(tmp_path, http)
    elements, error, cached = svc.query("query", read_timeout=30)
    assert elements == [{"type": "way", "id": 1}]
    assert error is None and cached is False
    assert [call[0] for call in http.calls] == ["https://mirror/slow", "https://mirror/fast"]
    assert all(call[1] == (5, 30) for call in http.calls)
    assert svc.health["https://mirror/slow"]["fails"] == 1


def test_fresh_cache_avoids_network(tmp_path):
    http = RotatingHttp()
    cache = {"known": {"timestamp": time.time(), "elements": [1]}}
    svc = service(tmp_path, http, cache)
    assert svc.query("query", cache_key="known") == ([1], None, True)
    assert http.calls == []


def test_stale_cache_is_fallback_when_all_mirrors_fail(tmp_path):
    class Failing:
        def post(self, *args, **kwargs): raise requests.exceptions.Timeout("down")
    cache = {"known": {"timestamp": 0, "elements": ["stale"]}}
    svc = service(tmp_path, Failing(), cache)
    elements, error, cached = svc.query("query", cache_key="known")
    assert elements == ["stale"] and error and cached is True


def test_persistent_cache_roundtrip(tmp_path):
    svc = service(tmp_path, RotatingHttp(), {"a": {"timestamp": 1, "elements": [1]}})
    svc.save_cache()
    restored = service(tmp_path, RotatingHttp(), {})
    assert restored.load_cache() == 1
    assert restored.cache["a"]["elements"] == [1]


def test_empty_http_200_rotates_to_next_mirror(tmp_path):
    class EmptyThenGood:
        def __init__(self): self.calls = 0
        def post(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                class Empty:
                    status_code = 200
                    text = ""
                    def json(self): return {"elements": []}
                return Empty()
            return Response()
    http = EmptyThenGood(); svc = service(tmp_path, http)
    elements, error, cached = svc.query("query")
    assert elements and error is None and cached is False
    assert http.calls == 2


def test_http_error_includes_response_excerpt(tmp_path):
    class Rejected:
        def post(self, *args, **kwargs):
            class Result:
                status_code = 406
                text = "Not acceptable: invalid client headers"
            return Result()
    svc = service(tmp_path, Rejected())
    elements, error, cached = svc.query("query")
    assert elements == [] and cached is False
    assert "HTTP 406" in error
    assert "invalid client headers" in error


def test_new_stage_can_bypass_previous_stage_cooldown_once(tmp_path):
    class AlwaysFail:
        def __init__(self): self.calls = 0
        def post(self, *args, **kwargs):
            self.calls += 1
            raise requests.exceptions.Timeout("down")
    http = AlwaysFail(); svc = service(tmp_path, http)
    svc.query("stage-1", cycle_id="load-stage-1")
    first_calls = http.calls
    svc.query("stage-2", cycle_id="load-stage-2", ignore_cooldown=True)
    assert first_calls == 2
    assert http.calls == 4


def test_attempt_telemetry_and_timeout_latency_are_recorded(tmp_path):
    class TimeoutHttp:
        def post(self, *args, **kwargs): raise requests.exceptions.Timeout("down")
    svc = service(tmp_path, TimeoutHttp())
    svc.query("query", cycle_id="cycle")
    for mirror in svc.health.values():
        assert mirror["last_attempt_at"] > 0
        assert mirror["last_latency_seconds"] is not None
        assert mirror["attempt_in_progress"] is False
