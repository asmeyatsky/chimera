"""Tests for centralized logging."""

import json
import logging
import pytest
from chimera.infrastructure.logging import configure_logging, JSONFormatter


class TestConfigureLogging:
    def test_default_level(self):
        configure_logging(level=logging.INFO)
        logger = logging.getLogger("chimera")
        assert logger.level == logging.INFO

    def test_debug_level(self):
        configure_logging(level=logging.DEBUG)
        logger = logging.getLogger("chimera")
        assert logger.level == logging.DEBUG

    def test_warning_level(self):
        configure_logging(level=logging.WARNING)
        logger = logging.getLogger("chimera")
        assert logger.level == logging.WARNING

    def test_json_format(self):
        configure_logging(level=logging.INFO, json_format=True)
        logger = logging.getLogger("chimera")
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0].formatter, JSONFormatter)

    def test_human_format(self):
        configure_logging(level=logging.INFO, json_format=False)
        logger = logging.getLogger("chimera")
        assert len(logger.handlers) == 1
        assert not isinstance(logger.handlers[0].formatter, JSONFormatter)

    def test_replaces_handlers(self):
        configure_logging(level=logging.INFO)
        configure_logging(level=logging.DEBUG)
        logger = logging.getLogger("chimera")
        assert len(logger.handlers) == 1


class TestJSONFormatter:
    def test_format_basic(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="hello world",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["message"] == "hello world"
        assert data["level"] == "INFO"
        assert data["logger"] == "test"
        assert "timestamp" in data

    def test_format_with_exception(self):
        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="error occurred",
            args=(),
            exc_info=exc_info,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert "exception" in data
        assert "ValueError" in data["exception"]
