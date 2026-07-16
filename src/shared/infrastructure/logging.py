"""Structured logging configuration for GHOS.

Provides JSON-formatted logs for production and colored console for development.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any


class StructuredFormatter(logging.Formatter):
    """JSON log formatter for production.

    Produces structured JSON log entries for log aggregation tools.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
            }

        # Add extra fields from record
        for key, value in getattr(record, "extra_fields", {}).items():
            log_entry[key] = value

        return json.dumps(log_entry, default=str)


class ColoredConsoleFormatter(logging.Formatter):
    """Colorized console formatter for development.

    Uses ANSI color codes for log level highlighting.
    """

    COLORS = {
        "DEBUG": "\033[36m",      # Cyan
        "INFO": "\033[32m",       # Green
        "WARNING": "\033[33m",    # Yellow
        "ERROR": "\033[31m",      # Red
        "CRITICAL": "\033[1;31m", # Bold Red
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def configure_logging() -> None:
    """Configure the root logger for GHOS.

    - Production: JSON format (GHOS_ENV=production)
    - Development: Colored console (default)
    """
    env = os.getenv("GHOS_ENV", "development")
    level = os.getenv("GHOS_LOG_LEVEL", "INFO").upper()

    handler = logging.StreamHandler(sys.stdout)

    if env == "production":
        formatter = StructuredFormatter()
    else:
        formatter = ColoredConsoleFormatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )

    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    # Remove default handlers to avoid duplicate output
    root_logger.handlers.clear()
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger with consistent configuration.

    Args:
        name: Logger name (typically __name__).

    Returns:
        Configured Logger instance.
    """
    return logging.getLogger(name)
