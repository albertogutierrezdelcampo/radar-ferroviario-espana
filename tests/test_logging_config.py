import logging

from radar.logging_config import RECENT_ERRORS, configure_logging


def test_logging_configuration_is_idempotent():
    logger = configure_logging()
    handler_count = len(logger.handlers)
    assert configure_logging() is logger
    assert len(logger.handlers) == handler_count


def test_warning_is_exposed_to_diagnostics_buffer():
    logger = configure_logging()
    logger.warning("phase-3-test-warning")
    assert any("phase-3-test-warning" in item["message"] for item in RECENT_ERRORS)
