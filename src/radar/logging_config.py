"""Central logging configuration for the application and diagnostics API."""
from __future__ import annotations

import logging
import os
import threading
import traceback
from collections import deque
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from radar.config import BASE_DIR
from radar.redaction import sanitize_text

LOG_DIR = Path(BASE_DIR) / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
ERROR_LOG_FILE = os.getenv("RADAR_LOG_FILE", str(LOG_DIR / "radar_errors.log"))
RECENT_ERRORS = deque(maxlen=200)
LOG_FORMAT = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(threadName)s | %(name)s | %(message)s"
)


class RedactingFilter(logging.Filter):
    """Sanitize the final formatted message before handlers persist or expose it."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = sanitize_text(record.getMessage())
        record.args = ()
        return True


class RecentErrorHandler(logging.Handler):
    """Keeps the latest warnings and errors available to the diagnostics UI."""

    def emit(self, record: logging.LogRecord) -> None:
        """Perform the documented application operation while preserving current API contracts.

        Parameters are validated or normalized by the function; relevant inputs: ``record``.
        """
        if record.levelno < logging.WARNING:
            return
        try:
            RECENT_ERRORS.appendleft({
                "timestamp": datetime.fromtimestamp(record.created).isoformat(timespec="seconds"),
                "level": record.levelname,
                "logger": record.name,
                "message": self.format(record),
            })
        except Exception:
            self.handleError(record)


def configure_logging() -> logging.Logger:
    """Configure the radar logger once, safely across repeated imports."""
    logger = logging.getLogger("radar")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if getattr(logger, "_radar_configured", False):
        return logger

    file_handler = RotatingFileHandler(
        ERROR_LOG_FILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.WARNING)
    file_handler.addFilter(RedactingFilter())
    file_handler.setFormatter(LOG_FORMAT)

    recent_handler = RecentErrorHandler()
    recent_handler.setLevel(logging.WARNING)
    recent_handler.addFilter(RedactingFilter())
    recent_handler.setFormatter(LOG_FORMAT)

    logger.addHandler(file_handler)
    logger.addHandler(recent_handler)
    logger._radar_configured = True
    return logger


APP_LOGGER = configure_logging()


def log_exception(context: str, exc: BaseException) -> None:
    """Perform the documented application operation while preserving current API contracts.

    Parameters are validated or normalized by the function; relevant inputs: ``context``, ``exc``.
    """
    APP_LOGGER.error("%s: %s\n%s", context, exc, traceback.format_exc())


def thread_exception_handler(args: threading.ExceptHookArgs) -> None:
    """Perform the documented application operation while preserving current API contracts.

    Parameters are validated or normalized by the function; relevant inputs: ``args``.
    """
    APP_LOGGER.error(
        "Excepción no controlada en hilo %s: %s",
        getattr(args.thread, "name", "N/D"),
        args.exc_value,
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )


def install_thread_exception_handler() -> None:
    """Perform the documented application operation while preserving current API contracts.
    """
    threading.excepthook = thread_exception_handler
