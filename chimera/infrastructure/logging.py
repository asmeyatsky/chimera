"""
Centralized Logging

Architectural Intent:
- Provides structured JSON logging for all Chimera components
- Centralizes log configuration to avoid scattered print() calls
- Supports configurable log levels via CLI flags (--verbose, --debug)
"""

import json
import logging
import sys
from datetime import datetime, UTC
from typing import Optional


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def configure_logging(
    level: int = logging.INFO,
    json_format: bool = False,
) -> None:
    """Configure logging for the Chimera application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, etc.)
        json_format: If True, use JSON structured output. Otherwise human-readable.
    """
    root = logging.getLogger("chimera")
    root.setLevel(level)

    # Remove existing handlers
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)

    if json_format:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )

    root.addHandler(handler)
