"""Resilient Overpass query service with stale-cache fallback and mirror rotation."""
from __future__ import annotations

import hashlib
import threading
import time
from pathlib import Path
from typing import Any, Callable

import requests

from radar.cache_store import read_json, write_json_atomic

StatusCallback = Callable[[str], None]


class OverpassService:
    def __init__(self, *, endpoints, cache, health, inflight, lock, http, cache_file,
                 cache_ttl, failure_cooldown, logger):
        """Perform the documented application operation while preserving current API contracts.
        """
        self.endpoints = list(endpoints)
        self.cache = cache
        self.health = health
        self.inflight = inflight
        self.lock = lock
        self.http = http
        self.cache_file = Path(cache_file)
        self.cache_ttl = cache_ttl
        self.failure_cooldown = failure_cooldown
        self.logger = logger

    def load_cache(self) -> int:
        """Load and normalize the requested resource while updating isolated application state.
        """
        data = read_json(self.cache_file, {})
        valid = {str(k): v for k, v in data.items()
                 if isinstance(v, dict) and isinstance(v.get("elements"), list)}
        with self.lock:
            self.cache.clear()
            self.cache.update(valid)
        return len(valid)

    def save_cache(self) -> None:
        """Persist the supplied state safely to its configured local destination.
        """
        with self.lock:
            snapshot = dict(self.cache)
        write_json_atomic(self.cache_file, snapshot)

    def query(self, query_str: str, *, read_timeout: int = 30, cache_key: str | None = None,
              status: StatusCallback | None = None, ignore_cooldown: bool = False,
              cycle_id: str | None = None):
        """Perform the documented application operation while preserving current API contracts.

        Parameters are validated or normalized by the function; relevant inputs: ``query_str``.
        """
        key = cache_key or hashlib.sha256(query_str.encode()).hexdigest()
        now = time.time()
        with self.lock:
            cached = self.cache.get(key)
            if cached and now - cached.get("timestamp", 0) < self.cache_ttl:
                return cached.get("elements", []), None, True
            event = self.inflight.get(key)
            owner = event is None
            if owner:
                event = threading.Event(); self.inflight[key] = event
        if not owner:
            event.wait(timeout=max(45, len(self.endpoints) * (read_timeout + 7)))
            with self.lock: concurrent = self.cache.get(key)
            return ((concurrent.get("elements", []), None, True) if concurrent
                    else ([], "consulta concurrente agotada", False))

        stale_elements = cached.get("elements", []) if cached else []
        last_error = "sin mirrors disponibles"
        try:
            def rank(url):
                """Perform the documented application operation while preserving current API contracts.

                Parameters are validated or normalized by the function; relevant inputs: ``url``.
                """
                h = self.health[url]
                success_rank = 0 if h.get("last_success_at", 0) else 1
                latency = h.get("last_latency_seconds")
                return (success_rank, latency if latency is not None else 9999, h["fails"],
                        self.endpoints.index(url))
            available = sorted(self.endpoints, key=rank)
            attempted = 0
            for index, endpoint in enumerate(available, start=1):
                mirror = self.health[endpoint]
                attempted_in_cycle = cycle_id and mirror.get("last_cycle_id") == cycle_id
                if mirror["retry_after"] > time.time() and not (ignore_cooldown and not attempted_in_cycle):
                    continue
                attempted += 1
                if status: status(f"Consultando Overpass {index}/{len(available)}: {endpoint}")
                started = time.monotonic()
                mirror.update(last_attempt_at=time.time(), attempt_started_at=time.time(),
                              attempt_in_progress=True, last_cycle_id=cycle_id)
                try:
                    response = self.http.post(endpoint, data={"data": query_str},
                                              timeout=(5, read_timeout))
                    if response.status_code == 200:
                        elements = response.json().get("elements", [])
                        if elements:
                            mirror.update(fails=0, retry_after=0.0, last_error=None,
                                          last_success_at=time.time())
                            with self.lock:
                                self.cache[key] = {"timestamp": time.time(), "elements": elements}
                            self.save_cache(); return elements, None, False
                        last_error = f"{endpoint}: HTTP 200 sin elementos"
                    else:
                        body = " ".join(response.text.strip().split())[:500]
                        last_error = f"{endpoint}: HTTP {response.status_code}" + (f": {body}" if body else "")
                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError,
                        requests.exceptions.SSLError) as exc:
                    last_error = f"{endpoint}: {exc}"
                except Exception as exc:
                    last_error = f"{endpoint}: {exc}"
                finally:
                    mirror["last_latency_seconds"] = round(time.monotonic() - started, 2)
                    mirror["attempt_in_progress"] = False
                mirror["fails"] += 1; mirror["last_error"] = last_error
                mirror["retry_after"] = time.time() + min(900, self.failure_cooldown * mirror["fails"])
                self.logger.warning("Overpass: %s; mirror en pausa %ss", last_error,
                                    int(mirror["retry_after"] - time.time()))
            if attempted == 0: last_error = "todos los mirrors están en cooldown"
            if stale_elements:
                self.logger.warning("Overpass: usando caché caducada tras fallo: %s", last_error)
                return stale_elements, last_error, True
            return [], last_error, False
        finally:
            with self.lock:
                self.inflight.pop(key, None); event.set()

    def diagnostics(self) -> list[dict[str, Any]]:
        """Perform the documented application operation while preserving current API contracts.
        """
        now = time.time()
        return [{
            "url": url,
            "fails": state["fails"],
            "cooldown_seconds": max(0, int(state["retry_after"] - now)),
            "last_latency_seconds": state.get("last_latency_seconds"),
            "last_attempt_at": state.get("last_attempt_at", 0),
            "last_success_at": state.get("last_success_at", 0),
            "last_error": state.get("last_error"),
            "attempt_in_progress": state.get("attempt_in_progress", False),
            "attempt_elapsed_seconds": (
                round(now - state.get("attempt_started_at", now), 1)
                if state.get("attempt_in_progress") else 0
            ),
        } for url, state in self.health.items()]
