"""Unit tests for configuration management."""

import os
import pytest
from decimal import Decimal

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from weighing_parser.config import (
    ParserSettings,
    get_settings,
    configure,
    reset_settings,
)


class TestParserSettings:
    """Tests for ParserSettings."""

    def setup_method(self):
        """Reset settings before each test."""
        reset_settings()
        # Clear any test environment variables
        for key in list(os.environ.keys()):
            if key.startswith("WEIGHING_PARSER_"):
                del os.environ[key]

    def teardown_method(self):
        """Clean up after each test."""
        reset_settings()
        for key in list(os.environ.keys()):
            if key.startswith("WEIGHING_PARSER_"):
                del os.environ[key]

    def test_default_values(self):
        """Test default configuration values."""
        settings = ParserSettings()
        assert settings.weight_tolerance_kg == Decimal("10")
        assert settings.min_confidence == 0.5
        assert settings.log_format == "json"
        assert settings.log_level == "INFO"
        assert settings.max_workers == 4

    def test_from_env(self):
        """Test loading settings from environment variables."""
        os.environ["WEIGHING_PARSER_WEIGHT_TOLERANCE_KG"] = "20"
        os.environ["WEIGHING_PARSER_MIN_CONFIDENCE"] = "0.7"
        os.environ["WEIGHING_PARSER_LOG_FORMAT"] = "text"
        os.environ["WEIGHING_PARSER_LOG_LEVEL"] = "DEBUG"
        os.environ["WEIGHING_PARSER_MAX_WORKERS"] = "8"

        settings = ParserSettings.from_env()

        assert settings.weight_tolerance_kg == Decimal("20")
        assert settings.min_confidence == 0.7
        assert settings.log_format == "text"
        assert settings.log_level == "DEBUG"
        assert settings.max_workers == 8

    def test_with_overrides(self):
        """Test creating settings with overrides (DI pattern)."""
        base_settings = ParserSettings()
        overridden = base_settings.with_overrides(
            weight_tolerance_kg=Decimal("15"),
            min_confidence=0.8,
        )

        assert overridden.weight_tolerance_kg == Decimal("15")
        assert overridden.min_confidence == 0.8
        # Unchanged values
        assert overridden.log_format == "json"
        assert overridden.max_workers == 4


class TestGlobalSettings:
    """Tests for global settings management."""

    def setup_method(self):
        """Reset settings before each test."""
        reset_settings()
        for key in list(os.environ.keys()):
            if key.startswith("WEIGHING_PARSER_"):
                del os.environ[key]

    def teardown_method(self):
        """Clean up after each test."""
        reset_settings()
        for key in list(os.environ.keys()):
            if key.startswith("WEIGHING_PARSER_"):
                del os.environ[key]

    def test_get_settings_lazy_init(self):
        """Test that get_settings initializes lazily."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2  # Same instance

    def test_configure_overrides_global(self):
        """Test that configure() sets global settings."""
        custom = ParserSettings(weight_tolerance_kg=Decimal("50"))
        configure(custom)

        settings = get_settings()
        assert settings.weight_tolerance_kg == Decimal("50")

    def test_reset_settings(self):
        """Test that reset_settings clears cached settings."""
        # Set custom settings
        custom = ParserSettings(weight_tolerance_kg=Decimal("99"))
        configure(custom)
        assert get_settings().weight_tolerance_kg == Decimal("99")

        # Reset
        reset_settings()

        # Should get fresh settings with defaults
        settings = get_settings()
        assert settings.weight_tolerance_kg == Decimal("10")


class TestSettingsValidation:
    """Tests for settings validation."""

    def test_min_confidence_range(self):
        """Test that min_confidence must be between 0 and 1."""
        # Valid values
        ParserSettings(min_confidence=0.0)
        ParserSettings(min_confidence=0.5)
        ParserSettings(min_confidence=1.0)

        # Invalid values
        with pytest.raises(Exception):
            ParserSettings(min_confidence=-0.1)
        with pytest.raises(Exception):
            ParserSettings(min_confidence=1.1)

    def test_log_format_values(self):
        """Test that log_format must be 'json' or 'text'."""
        # Valid values
        ParserSettings(log_format="json")
        ParserSettings(log_format="text")

        # Invalid values
        with pytest.raises(Exception):
            ParserSettings(log_format="xml")

    def test_max_workers_range(self):
        """Test that max_workers must be positive."""
        # Valid values
        ParserSettings(max_workers=1)
        ParserSettings(max_workers=32)

        # Invalid values
        with pytest.raises(Exception):
            ParserSettings(max_workers=0)
        with pytest.raises(Exception):
            ParserSettings(max_workers=33)
