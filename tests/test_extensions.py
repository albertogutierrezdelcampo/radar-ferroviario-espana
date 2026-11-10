from radar.extensions import build_http_session


def test_http_session_has_headers_and_adapters():
    session = build_http_session(
        total=2, connect=2, read=1, backoff=0.5,
        methods=("GET",), pool_size=3,
    )
    assert "RenfeAdifTracker" in session.headers["User-Agent"]
    assert "http://" in session.adapters
    assert "https://" in session.adapters
    retry = session.adapters["https://"].max_retries
    assert retry.total == 2
    assert "GET" in retry.allowed_methods
    assert retry.respect_retry_after_header is True
