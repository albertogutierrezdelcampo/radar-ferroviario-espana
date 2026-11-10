"""Shared infrastructure clients configured with bounded retries and pooling."""
from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from radar.config import HEADERS


def build_http_session(*, total: int, connect: int, read: int, backoff: float,
                       methods: tuple[str, ...], pool_size: int) -> requests.Session:
    retry = Retry(
        total=total,
        connect=connect,
        read=read,
        backoff_factor=backoff,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(methods),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(
        max_retries=retry, pool_connections=pool_size, pool_maxsize=pool_size
    )
    session = requests.Session()
    session.headers.update(HEADERS)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


DEFAULT_HTTP = build_http_session(
    total=2, connect=2, read=1, backoff=0.5, methods=("GET",), pool_size=8
)
OVERPASS_HTTP = build_http_session(
    total=2, connect=2, read=1, backoff=0.8, methods=("POST",), pool_size=8
)
OPERATOR_HTTP = build_http_session(
    total=3, connect=3, read=2, backoff=1.0, methods=("GET",), pool_size=4
)
