"""Integration tests for refresh, operator configuration and administrative routes."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


class ImmediateThread:
    created = []
    def __init__(self, target=None, args=(), kwargs=None, **metadata):
        self.target = target; self.args = args; self.kwargs = kwargs or {}; self.metadata = metadata
        self.__class__.created.append(self)
    def start(self):
        return None


def test_refresh_schedules_open_access_and_available_metro_jobs(client, appmod, preserve_runtime_state, monkeypatch):
    ImmediateThread.created = []
    monkeypatch.setattr(appmod.threading, "Thread", ImmediateThread)
    first_key = next(iter(appmod.METRO_CACHE))
    appmod.METRO_CACHE[first_key]["loading"] = True
    response = client.post("/api/feeds/refresh")
    assert response.status_code == 200 and response.get_json()["success"] is True
    targets = [job.target for job in ImmediateThread.created]
    assert targets.count(appmod.load_operator_gtfs) == len(appmod.OPEN_ACCESS_GTFS)
    assert targets.count(appmod.load_metro_gtfs) == len(appmod.METRO_CACHE) - 1


def test_operator_config_get_never_returns_token(client, appmod, monkeypatch):
    monkeypatch.setattr(appmod, "operator_token", lambda *a: "secret-value")
    body = client.get("/api/operators/config").get_json()
    assert body["ouigo_configured"] is True
    assert "secret-value" not in str(body)


@pytest.mark.parametrize("token", ["", "short", "x" * 513])
def test_operator_config_rejects_invalid_token(client, token):
    response = client.post("/api/operators/config", json={"token": token})
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_operator_config_post_persists_and_schedules_reload(client, appmod, preserve_runtime_state, monkeypatch):
    saved = []
    ImmediateThread.created = []
    monkeypatch.setattr(appmod, "save_operator_token", lambda key, token: saved.append((key, token)))
    monkeypatch.setattr(appmod.threading, "Thread", ImmediateThread)
    response = client.post("/api/operators/config", json={"token": "valid-token-123"})
    assert response.status_code == 200 and response.get_json()["success"] is True
    assert saved == [("ouigo", "valid-token-123")]
    assert len(ImmediateThread.created) == 1
    assert ImmediateThread.created[0].target is appmod.load_operator_gtfs


def test_operator_config_delete_clears_state(client, appmod, preserve_runtime_state, monkeypatch):
    saved = []
    monkeypatch.setattr(appmod, "save_operator_token", lambda key, token: saved.append((key, token)))
    appmod.OPEN_ACCESS_CACHE["ouigo"].update(loaded=True, error=None)
    response = client.delete("/api/operators/config")
    assert response.status_code == 200 and saved == [("ouigo", "")]
    assert appmod.OPEN_ACCESS_CACHE["ouigo"]["loaded"] is False


def test_diagnostics_error_clear_uses_temporary_file(client, appmod, monkeypatch, tmp_path):
    log = tmp_path / "radar.log"; log.write_text("secret\n", encoding="utf-8")
    monkeypatch.setitem(appmod.clear_error_log.__globals__, "ERROR_LOG_FILE", str(log))
    appmod.RECENT_ERRORS.append({"message": "old"})
    response = client.delete("/api/diagnostics/errors")
    assert response.status_code == 200 and response.get_json()["success"] is True
    assert log.read_text(encoding="utf-8") == ""
    assert len(appmod.RECENT_ERRORS) == 0
