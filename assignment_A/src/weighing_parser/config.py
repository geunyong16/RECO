"""Configuration management for weighing parser.

Supports configuration via:
1. Environment variables
2. Dependency Injection (constructor parameters)
3. Default values

Environment Variables:
    WEIGHING_PARSER_TOLERANCE_KG: Weight validation tolerance in kg (default: 10)
    WEIGHING_PARSER_MIN_CONFIDENCE: Minimum confidence threshold (default: 0.5)
    WEIGHING_PARSER_LOG_FORMAT: Log format - 'json' or 'text' (default: json)
    WEIGHING_PARSER_LOG_LEVEL: Log level (default: INFO)
    WEIGHING_PARSER_MAX_WORKERS: Max async workers (default: 4)
"""

import os
from decimal import Decimal
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings


class ConfigurationError(Exception):
    """Raised when configuration validation fails."""

    def __init__(self, field: str, value, message: str):
        self.field = field
        self.value = value
        super().__init__(f"Invalid configuration for '{field}': {message} (got: {value})")


class ParserSettings(BaseSettings):
    """Parser configuration with environment variable support.

    Settings are loaded from environment variables with WEIGHING_PARSER_ prefix.
    All values are validated on load to ensure safe operation.
    """

    weight_tolerance_kg: Decimal = Field(
        default=Decimal("10"),
        description="Weight validation tolerance in kg (must be >= 0)"
    )
    min_confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for extractions (0.0 - 1.0)"
    )
    log_format: Literal["json", "text"] = Field(
        default="json",
        description="Log format: 'json' for structured, 'text' for human-readable"
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level"
    )
    max_workers: int = Field(
        default=4,
        ge=1,
        le=32,
        description="Maximum number of async worker threads (1-32)"
    )

    model_config = {
        "env_prefix": "WEIGHING_PARSER_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @field_validator("weight_tolerance_kg")
    @classmethod
    def validate_weight_tolerance(cls, v: Decimal) -> Decimal:
        """Ensure weight tolerance is non-negative."""
        if v < 0:
            raise ValueError("Weight tolerance must be >= 0 kg")
        if v > 1000:
            raise ValueError("Weight tolerance exceeds reasonable limit (1000 kg)")
        return v

    @field_validator("min_confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Ensure confidence is within valid range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return v

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, v: str) -> str:
        """Normalize log level to uppercase."""
        if isinstance(v, str):
            return v.upper()
        return v

    @model_validator(mode="after")
    def validate_settings_combination(self) -> "ParserSettings":
        """Validate combinations of settings that may have interdependencies."""
        # Warn if tolerance is very high compared to typical weights
        if self.weight_tolerance_kg > 100:
            import warnings
            warnings.warn(
                f"Weight tolerance of {self.weight_tolerance_kg}kg is unusually high. "
                "This may mask data quality issues.",
                UserWarning
            )

        # Ensure confidence threshold is reasonable
        if self.min_confidence < 0.3:
            import warnings
            warnings.warn(
                f"Very low confidence threshold ({self.min_confidence}). "
                "Results may include unreliable extractions.",
                UserWarning
            )

        return self

    @classmethod
    def from_env(cls) -> "ParserSettings":
        """Create settings from environment variables."""
        return cls()

    def with_overrides(
        self,
        weight_tolerance_kg: Optional[Decimal] = None,
        min_confidence: Optional[float] = None,
        log_format: Optional[str] = None,
        log_level: Optional[str] = None,
        max_workers: Optional[int] = None,
    ) -> "ParserSettings":
        """Create new settings with overridden values (DI pattern)."""
        return ParserSettings(
            weight_tolerance_kg=weight_tolerance_kg or self.weight_tolerance_kg,
            min_confidence=min_confidence if min_confidence is not None else self.min_confidence,
            log_format=log_format or self.log_format,
            log_level=log_level or self.log_level,
            max_workers=max_workers or self.max_workers,
        )


# Global default settings instance (can be overridden)
_settings: Optional[ParserSettings] = None


def get_settings() -> ParserSettings:
    """Get current settings (lazy initialization from env)."""
    global _settings
    if _settings is None:
        _settings = ParserSettings.from_env()
    return _settings


def configure(settings: ParserSettings) -> None:
    """Configure global settings (useful for testing or DI)."""
    global _settings
    _settings = settings


def reset_settings() -> None:
    """Reset settings to reload from environment (useful for testing)."""
    global _settings
    _settings = None
