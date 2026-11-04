"""Logging setup: one general log and one errors-only log.

Both files rotate at midnight and keep only the last N days
(default 7) so the log folder never grows without bound.
"""

from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

ROOT_LOGGER_NAME = "file_organizer"
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(log_dir: Path, retention_days: int = 7, verbose: bool = False) -> logging.Logger:
    """Configure and return the application's root logger.

    Args:
        log_dir: Directory where ``organizer.log`` and ``errors.log`` live.
        retention_days: Number of daily log files to keep.
        verbose: When True, the general log also records DEBUG messages.

    Returns:
        The configured ``file_organizer`` logger. Child loggers such as
        ``file_organizer.scanner`` automatically use its handlers.
    """
    logger = logging.getLogger(ROOT_LOGGER_NAME)
    if logger.handlers:  # already configured (e.g. called twice in tests)
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

    try:
        log_dir.mkdir(parents=True, exist_ok=True)

        main_handler = TimedRotatingFileHandler(
            log_dir / "organizer.log", when="midnight",
            backupCount=retention_days, encoding="utf-8",
        )
        main_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
        main_handler.setFormatter(formatter)
        logger.addHandler(main_handler)

        error_handler = TimedRotatingFileHandler(
            log_dir / "errors.log", when="midnight",
            backupCount=retention_days, encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        logger.addHandler(error_handler)
    except OSError:
        # Logging must never stop the tool from working.
        logger.addHandler(logging.NullHandler())

    return logger
