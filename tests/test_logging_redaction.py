import logging

from radar.logging_config import RedactingFilter


def test_logging_filter_removes_signed_query_and_secret_arguments():
    record = logging.LogRecord(
        "radar", logging.WARNING, __file__, 1,
        "url=%s token=%s", (
            "https://x.test/f.zip?X-Amz-Signature=abc&X-Amz-Credential=AKIA",
            "super-secret",
        ), None,
    )
    assert RedactingFilter().filter(record)
    message = record.getMessage()
    assert "abc" not in message and "AKIA" not in message and "super-secret" not in message
    assert "[REDACTED]" in message
