"""Robust NAP and direct-download acquisition for static GTFS archives.

The Spanish National Access Point can return a ZIP directly, a redirect, JSON
containing a temporary URL, or plain text. This service normalizes those forms,
validates GTFS bytes before replacing the persistent cache, and preserves a
previously valid cache when every remote strategy fails.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from radar.gtfs import GtfsValidationError, open_gtfs_archive
from radar.redaction import sanitize_text, sanitize_url


@dataclass(slots=True)
class GtfsFetchResult:
    """Describe one GTFS acquisition attempt without hiding degraded operation."""

    content: bytes | None = None
    source: str | None = None
    status: str = "failed"
    using_cache: bool = False
    stale: bool = False
    cache_age_seconds: int | None = None
    errors: list[str] = field(default_factory=list)
    attempts: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Return whether validated GTFS bytes are available to the caller."""
        return self.content is not None


def find_download_url(payload: Any) -> str | None:
    """Recursively locate the first HTTP(S) URL in typical NAP response shapes."""
    if isinstance(payload, str):
        value = payload.strip().strip('"').strip("'")
        if value.startswith(("https://", "http://")):
            return value
        try:
            return find_download_url(json.loads(value))
        except (json.JSONDecodeError, TypeError):
            return None
    if isinstance(payload, dict):
        preferred = (
            "url", "downloadUrl", "downloadURL", "download_url", "downloadLink",
            "link", "href", "result", "data", "value", "file", "fichero",
        )
        for key in preferred:
            if key in payload and (found := find_download_url(payload[key])):
                return found
        for value in payload.values():
            if found := find_download_url(value):
                return found
    if isinstance(payload, list):
        for value in payload:
            if found := find_download_url(value):
                return found
    return None


def validate_gtfs_bytes(content: bytes) -> bytes:
    """Return GTFS bytes after ZIP and mandatory-table validation."""
    open_gtfs_archive(content, include=("stops.txt", "routes.txt", "trips.txt", "stop_times.txt"))
    return content


def write_bytes_atomic(path: str | Path, content: bytes) -> None:
    """Persist bytes atomically so an interrupted refresh cannot destroy cache."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    with temporary.open("wb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)


class NapGtfsService:
    """Acquire validated GTFS using fresh cache, NAP, fallbacks and stale cache."""

    def __init__(self, http, *, logger, timeout=(10, 45), endpoint_template=None):
        self.http = http
        self.logger = logger
        self.timeout = timeout
        self.endpoint_template = endpoint_template or (
            "https://nap.transportes.gob.es/api/Fichero/downloadLink/{dataset_id}"
        )

    @staticmethod
    def _preview(response, limit=300) -> str:
        text = getattr(response, "text", "") or ""
        return " ".join(text.split())[:limit]

    @staticmethod
    def _safe_url(url: str) -> bool:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def _validated_response_bytes(self, response, label: str, attempts, errors) -> bytes | None:
        status = int(getattr(response, "status_code", 0))
        content = bytes(getattr(response, "content", b"") or b"")
        attempt = {"source": sanitize_url(label), "http_status": status, "bytes": len(content)}
        attempts.append(attempt)
        if status != 200:
            errors.append(sanitize_text(f"{label}: HTTP {status}: {self._preview(response)}".rstrip(": ")))
            return None
        if not content.startswith(b"PK"):
            return None
        try:
            return validate_gtfs_bytes(content)
        except GtfsValidationError as exc:
            errors.append(sanitize_text(f"{label}: ZIP no es GTFS válido: {exc}"))
            return None

    def _request(self, url: str, *, headers=None):
        return self.http.get(url, headers=headers, timeout=self.timeout, allow_redirects=True)

    def download_nap(self, dataset_id: int | str, token: str) -> GtfsFetchResult:
        """Resolve one NAP dataset and return validated bytes without writing cache."""
        result = GtfsFetchResult()
        endpoint = self.endpoint_template.format(dataset_id=dataset_id)
        try:
            response = self._request(endpoint, headers={"ApiKey": token})
            if content := self._validated_response_bytes(response, endpoint, result.attempts, result.errors):
                result.content, result.source, result.status = content, f"NAP {dataset_id} direct", "downloaded"
                return result
            if int(getattr(response, "status_code", 0)) != 200:
                return result
            try:
                payload = response.json()
            except Exception:
                payload = getattr(response, "text", "")
            link = find_download_url(payload)
            if not link or not self._safe_url(link):
                result.errors.append(
                    f"{endpoint}: HTTP 200 sin URL descargable: {self._preview(response)}"
                )
                return result
            download = self._request(link, headers={"ApiKey": token})
            if content := self._validated_response_bytes(download, link, result.attempts, result.errors):
                result.content, result.source, result.status = content, f"NAP {dataset_id} link", "downloaded"
            elif int(getattr(download, "status_code", 0)) == 200:
                result.errors.append(sanitize_text(f"{link}: respuesta no ZIP/GTFS: {self._preview(download)}"))
        except Exception as exc:
            result.errors.append(sanitize_text(f"{endpoint}: {exc}"))
        return result

    def download_direct(self, urls: Iterable[str]) -> GtfsFetchResult:
        """Try public fallback URLs in order and validate every successful response."""
        result = GtfsFetchResult()
        for url in urls:
            try:
                response = self._request(url)
                content = self._validated_response_bytes(response, url, result.attempts, result.errors)
                if content:
                    result.content, result.source, result.status = content, sanitize_url(url), "downloaded"
                    return result
                if int(getattr(response, "status_code", 0)) == 200:
                    result.errors.append(sanitize_text(f"{url}: respuesta no ZIP/GTFS: {self._preview(response)}"))
            except Exception as exc:
                result.errors.append(sanitize_text(f"{url}: {exc}"))
        return result

    def acquire(self, *, dataset_id, token, fallback_urls, cache_file, ttl, force=False) -> GtfsFetchResult:
        """Apply fresh-cache, NAP, direct-fallback and stale-cache acquisition policy."""
        cache_path = Path(cache_file)
        now = time.time()
        cached_content = None
        cache_age = None
        if cache_path.exists():
            try:
                cache_age = max(0, int(now - cache_path.stat().st_mtime))
                cached_content = validate_gtfs_bytes(cache_path.read_bytes())
            except (OSError, GtfsValidationError) as exc:
                cached_content = None
                cache_error = f"caché local inválida: {exc}"
            else:
                cache_error = None
        else:
            cache_error = None

        if cached_content is not None and not force and cache_age is not None and cache_age < ttl:
            return GtfsFetchResult(
                content=cached_content, source="cache", status="ready", using_cache=True,
                cache_age_seconds=cache_age,
            )

        errors = [cache_error] if cache_error else []
        attempts: list[dict[str, Any]] = []
        remote_results = []
        if dataset_id and token:
            remote_results.append(self.download_nap(dataset_id, token))
        elif dataset_id and not token:
            errors.append("API key NAP no configurada")
        remote_results.append(self.download_direct(fallback_urls))

        for remote in remote_results:
            errors.extend(remote.errors)
            attempts.extend(remote.attempts)
            if remote.ok:
                try:
                    write_bytes_atomic(cache_path, remote.content)
                except OSError as exc:
                    errors.append(f"no se pudo actualizar la caché: {exc}")
                remote.errors = errors
                remote.attempts = attempts
                remote.cache_age_seconds = 0
                return remote

        if cached_content is not None:
            return GtfsFetchResult(
                content=cached_content, source="stale-cache", status="stale",
                using_cache=True, stale=True, cache_age_seconds=cache_age,
                errors=errors + ["usando último GTFS válido"], attempts=attempts,
            )
        return GtfsFetchResult(errors=errors, attempts=attempts)
