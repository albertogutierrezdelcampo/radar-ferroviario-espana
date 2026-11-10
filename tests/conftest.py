"""Shared pytest bootstrap for root modules and src-layout packages."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import copy
import importlib
import pytest


@pytest.fixture(scope="session")
def appmod():
    """Import the compatibility entry point once without starting background jobs."""
    module = importlib.import_module("app")
    module.app.config.update(TESTING=True, PROPAGATE_EXCEPTIONS=False)
    return module


@pytest.fixture
def client(appmod, monkeypatch):
    """Return an isolated Flask client with network-starting hooks disabled."""
    monkeypatch.setattr(appmod, "ensure_background_threads", lambda: None)
    monkeypatch.setattr(appmod, "ensure_metro_feeds", lambda: None)
    monkeypatch.setattr(appmod, "ensure_operator_feeds", lambda: None)
    return appmod.app.test_client()


@pytest.fixture
def preserve_runtime_state(appmod):
    """Restore mutable caches after an integration test mutates global aliases."""
    targets = [
        appmod.RT_CACHE, appmod.STATIC_CACHE, appmod.ALERTS_CACHE,
        appmod.ADIF_CACHE, appmod.OPEN_ACCESS_CACHE, appmod.METRO_CACHE,
        appmod.OVERPASS_QUERY_CACHE, appmod.OVERPASS_ENDPOINT_HEALTH,
    ]
    snapshots = [copy.deepcopy(target) for target in targets]
    yield
    for target, snapshot in zip(targets, snapshots):
        target.clear()
        target.update(snapshot)
