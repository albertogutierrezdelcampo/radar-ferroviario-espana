"""Central redaction helpers for diagnostics, state snapshots and log messages."""
from __future__ import annotations

import re
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SENSITIVE_KEYS = frozenset({
    "apikey", "api_key", "token", "access_token", "refresh_token", "authorization",
    "password", "secret", "signature", "x-amz-signature", "x-amz-credential",
    "x-amz-security-token", "x-amz-date", "x-goog-signature", "x-goog-credential",
    "sig", "se", "sp", "sv",
})
SIGNED_QUERY_PREFIXES = ("x-amz-", "x-goog-")
REDACTED = "[REDACTED]"


def _sensitive_key(key: str) -> bool:
    normalized = str(key).strip().lower()
    return normalized in SENSITIVE_KEYS or normalized.startswith(SIGNED_QUERY_PREFIXES)


def sanitize_url(value: str) -> str:
    """Remove credentials, fragments and sensitive query values from an HTTP URL."""
    try:
        parsed = urlsplit(value)
    except (TypeError, ValueError):
        return str(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return str(value)
    hostname = parsed.hostname or ""
    try:
        parsed_port = parsed.port
    except ValueError:
        parsed_port = None
    port = f":{parsed_port}" if parsed_port else ""
    netloc = hostname + port
    safe_query = []
    for key, item in parse_qsl(parsed.query, keep_blank_values=True):
        safe_query.append((key, REDACTED if _sensitive_key(key) else item))
    return urlunsplit((parsed.scheme, netloc, parsed.path, urlencode(safe_query, doseq=True), ""))


_URL_RE = re.compile(r"https?://[^\s<>\"']+")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)(apikey|api_key|token|access_token|refresh_token|authorization|password|secret)"
    r"(\s*[:=]\s*)([^\s,;]+)"
)


def sanitize_text(value: Any) -> str:
    """Redact URLs and obvious secret assignments in arbitrary diagnostic text."""
    text = str(value)
    text = _URL_RE.sub(lambda match: sanitize_url(match.group(0)), text)
    return _SECRET_ASSIGNMENT_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", text)


def sanitize_data(value: Any) -> Any:
    """Recursively sanitize mappings and sequences while preserving JSON shape."""
    if isinstance(value, Mapping):
        sanitized = {}
        for key, item in value.items():
            sanitized[key] = REDACTED if _sensitive_key(str(key)) else sanitize_data(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_data(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_data(item) for item in value)
    if isinstance(value, str):
        return sanitize_text(value)
    return value
