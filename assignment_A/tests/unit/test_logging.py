"""Unit tests for structured logging."""

import io
import json
import pytest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from weighing_parser.logging import (
    configure_logging,
    get_logger,
    ParserLogger,
)


class TestConfigureLogging:
    """Tests for logging configuration."""

    def test_configure_json_format(self):
        """Test JSON format logging configuration."""
        stream = io.StringIO()
        configure_logging(log_level="INFO", log_format="json", stream=stream)

        logger = get_logger("test")
        logger.info("test_event", key="value")

        output = stream.getvalue()
        # Should be valid JSON
        assert output.strip()  # Not empty
        log_entry = json.loads(output.strip())
        assert log_entry["event"] == "test_event"
        assert log_entry["key"] == "value"
        assert log_entry["service"] == "weighing-parser"

    def test_configure_text_format(self):
        """Test text format logging configuration."""
        stream = io.StringIO()
        configure_logging(log_level="INFO", log_format="text", stream=stream)

        logger = get_logger("test")
        logger.info("test_event", key="value")

        output = stream.getvalue()
        # Text format should contain the event name
        assert "test_event" in output

    def test_log_level_filtering(self):
        """Test that log level filtering works."""
        stream = io.StringIO()
        configure_logging(log_level="WARNING", log_format="json", stream=stream)

        logger = get_logger("test")
        logger.info("info_event")  # Should be filtered
        logger.warning("warning_event")  # Should appear

        output = stream.getvalue()
        assert "info_event" not in output
        assert "warning_event" in output


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_with_name(self):
        """Test getting a named logger."""
        stream = io.StringIO()
        configure_logging(log_level="INFO", log_format="json", stream=stream)

        logger = get_logger("my_module")
        logger.info("test")

        output = stream.getvalue()
        log_entry = json.loads(output.strip())
        assert log_entry["logger"] == "my_module"

    def test_get_logger_without_name(self):
        """Test getting an unnamed logger."""
        stream = io.StringIO()
        configure_logging(log_level="INFO", log_format="json", stream=stream)

        logger = get_logger()
        logger.info("test")

        # Should still work
        output = stream.getvalue()
        assert "test" in output


class TestParserLogger:
    """Tests for domain-specific ParserLogger."""

    def setup_method(self):
        """Set up test stream."""
        self.stream = io.StringIO()
        configure_logging(log_level="DEBUG", log_format="json", stream=self.stream)
        self.logger = ParserLogger("test")

    def test_parsing_started(self):
        """Test parsing_started event."""
        self.logger.parsing_started(file_path="/path/to/file.json", file_count=3)

        output = self.stream.getvalue()
        log_entry = json.loads(output.strip())
        assert log_entry["event"] == "parsing_started"
        assert log_entry["file_path"] == "/path/to/file.json"
        assert log_entry["file_count"] == 3

    def test_parsing_completed(self):
        """Test parsing_completed event."""
        self.logger.parsing_completed(
            file_path="/path/to/file.json",
            duration_ms=125.5,
            success=True
        )

        output = self.stream.getvalue()
        log_entry = json.loads(output.strip())
        assert log_entry["event"] == "parsing_completed"
        assert log_entry["success"] is True
        assert log_entry["duration_ms"] == 125.5

    def test_extraction_failed(self):
        """Test extraction_failed event."""
        self.logger.extraction_failed(
            field="vehicle_number",
            error="Pattern not found"
        )

        output = self.stream.getvalue()
        log_entry = json.loads(output.strip())
        assert log_entry["event"] == "extraction_failed"
        assert log_entry["field"] == "vehicle_number"
        assert log_entry["error"] == "Pattern not found"
        assert log_entry["level"] == "warning"

    def test_validation_error(self):
        """Test validation_error event."""
        self.logger.validation_error(
            error_type="weight_invariant",
            message="Net weight mismatch"
        )

        output = self.stream.getvalue()
        log_entry = json.loads(output.strip())
        assert log_entry["event"] == "validation_error"
        assert log_entry["error_type"] == "weight_invariant"

    def test_parse_error(self):
        """Test parse_error event."""
        self.logger.parse_error(
            file_path="/path/to/file.json",
            error="Invalid JSON",
            error_type="JSONDecodeError"
        )

        output = self.stream.getvalue()
        log_entry = json.loads(output.strip())
        assert log_entry["event"] == "parse_error"
        assert log_entry["error_type"] == "JSONDecodeError"
        assert log_entry["level"] == "error"

    def test_batch_summary(self):
        """Test batch_summary event."""
        self.logger.batch_summary(
            total_files=10,
            successful=8,
            failed=2,
            with_warnings=3
        )

        output = self.stream.getvalue()
        log_entry = json.loads(output.strip())
        assert log_entry["event"] == "batch_summary"
        assert log_entry["total_files"] == 10
        assert log_entry["successful"] == 8
        assert log_entry["failed"] == 2
        assert log_entry["with_warnings"] == 3

    def test_extra_context(self):
        """Test that extra context is included."""
        self.logger.parsing_started(
            file_path="/path/to/file.json",
            custom_field="custom_value"
        )

        output = self.stream.getvalue()
        log_entry = json.loads(output.strip())
        assert log_entry["custom_field"] == "custom_value"


class TestStructuredLogFormat:
    """Tests for structured log format compliance."""

    def setup_method(self):
        """Set up test stream."""
        self.stream = io.StringIO()
        configure_logging(log_level="INFO", log_format="json", stream=self.stream)

    def test_iso_timestamp(self):
        """Test that timestamp is in ISO format."""
        logger = get_logger("test")
        logger.info("test")

        output = self.stream.getvalue()
        log_entry = json.loads(output.strip())
        # Should have timestamp field
        assert "timestamp" in log_entry
        # ISO format check (basic)
        assert "T" in log_entry["timestamp"] or "-" in log_entry["timestamp"]

    def test_service_context(self):
        """Test that service context is included."""
        logger = get_logger("test")
        logger.info("test")

        output = self.stream.getvalue()
        log_entry = json.loads(output.strip())
        assert log_entry["service"] == "weighing-parser"

    def test_elk_compatible_fields(self):
        """Test that logs have ELK-compatible fields."""
        logger = get_logger("my_module")
        logger.info("test_event", user_id=123)

        output = self.stream.getvalue()
        log_entry = json.loads(output.strip())

        # Required fields for ELK/Datadog
        assert "timestamp" in log_entry
        assert "level" in log_entry
        assert "logger" in log_entry
        assert "event" in log_entry
        assert "service" in log_entry
