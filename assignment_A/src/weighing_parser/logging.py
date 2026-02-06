"""Structured logging configuration for weighing parser.

Provides JSON-formatted structured logging compatible with:
- ELK Stack (Elasticsearch, Logstash, Kibana)
- Datadog
- AWS CloudWatch
- Google Cloud Logging

Usage:
    from weighing_parser.logging import get_logger, configure_logging

    # Configure at application startup
    configure_logging(log_level="INFO", log_format="json")

    # Get logger in modules
    logger = get_logger(__name__)

    # Log with structured context
    logger.info("parsing_started", file_path="/path/to/file.json", file_count=5)
    logger.warning("extraction_failed", field="vehicle_number", error=str(e))

Custom Backend Integration:
    from weighing_parser.logging import LoggingBackend, register_backend

    # Create custom backend for ELK/Datadog/etc.
    class ElkBackend(LoggingBackend):
        def __init__(self, host: str, port: int):
            self.host = host
            self.port = port

        def get_handler(self) -> logging.Handler:
            # Return your custom handler (e.g., python-logstash handler)
            from logstash_async.handler import AsynchronousLogstashHandler
            return AsynchronousLogstashHandler(self.host, self.port, database_path=None)

        def get_processors(self) -> list:
            return []  # Return custom structlog processors if needed

    # Register and configure
    register_backend("elk", ElkBackend("localhost", 5044))
    configure_logging(log_level="INFO", backend="elk")
"""

import logging
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Optional, TextIO

import structlog
from structlog.types import Processor


# =============================================================================
# Logging Backend Interface for External Systems
# =============================================================================


class LoggingBackend(ABC):
    """Abstract base class for custom logging backends.

    Implement this interface to integrate with external logging systems
    like ELK Stack, Datadog, Splunk, etc.

    Example:
        class DatadogBackend(LoggingBackend):
            def __init__(self, api_key: str, service: str):
                self.api_key = api_key
                self.service = service

            def get_handler(self) -> logging.Handler:
                from datadog_logger import DatadogLogHandler
                return DatadogLogHandler(api_key=self.api_key, service=self.service)

            def get_processors(self) -> list:
                return []  # Use default processors
    """

    @abstractmethod
    def get_handler(self) -> logging.Handler:
        """Return a logging.Handler instance for this backend.

        Returns:
            A configured logging.Handler that sends logs to the backend.
        """
        pass

    def get_processors(self) -> list[Processor]:
        """Return additional structlog processors for this backend.

        Override this method to add backend-specific processors.

        Returns:
            List of structlog processors (empty by default).
        """
        return []

    def get_formatter(self) -> Optional[logging.Formatter]:
        """Return a custom formatter for this backend.

        Override this method if your backend needs a specific log format.

        Returns:
            A logging.Formatter instance or None to use default.
        """
        return None


@dataclass
class LoggingConfig:
    """Configuration for logging setup.

    Attributes:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Output format - 'json' for structured, 'text' for console
        stream: Output stream for default handler
        service_name: Service name included in logs
        backend: Name of registered backend to use (optional)
        extra_processors: Additional structlog processors
        extra_context: Static context added to all log entries
    """

    log_level: str = "INFO"
    log_format: str = "json"
    stream: Optional[TextIO] = None
    service_name: str = "weighing-parser"
    backend: Optional[str] = None
    extra_processors: list[Processor] = field(default_factory=list)
    extra_context: dict = field(default_factory=dict)


# Backend registry
_backends: dict[str, LoggingBackend] = {}
_current_config: Optional[LoggingConfig] = None


def register_backend(name: str, backend: LoggingBackend) -> None:
    """Register a custom logging backend.

    Args:
        name: Unique name for the backend (e.g., "elk", "datadog", "splunk")
        backend: Backend instance implementing LoggingBackend interface

    Example:
        register_backend("elk", ElkBackend("localhost", 5044))
        configure_logging(log_level="INFO", backend="elk")
    """
    _backends[name] = backend


def unregister_backend(name: str) -> None:
    """Unregister a logging backend.

    Args:
        name: Name of the backend to remove
    """
    _backends.pop(name, None)


def get_registered_backends() -> list[str]:
    """Get list of registered backend names.

    Returns:
        List of registered backend names.
    """
    return list(_backends.keys())


def get_current_config() -> Optional[LoggingConfig]:
    """Get the current logging configuration.

    Returns:
        Current LoggingConfig or None if not configured.
    """
    return _current_config


def _create_service_context_processor(
    service_name: str, extra_context: Optional[dict] = None
) -> Callable:
    """Create a processor that adds service context to log entries.

    Args:
        service_name: Service name to include in logs
        extra_context: Additional static context to include

    Returns:
        A structlog processor function
    """
    extra = extra_context or {}

    def _add_service_context(
        logger: logging.Logger, method_name: str, event_dict: dict  # noqa: ARG001
    ) -> dict:
        """Add service context for log aggregation systems."""
        event_dict["service"] = service_name
        event_dict.update(extra)
        return event_dict

    return _add_service_context


def configure_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    stream: Optional[TextIO] = None,
    service_name: str = "weighing-parser",
    backend: Optional[str] = None,
    extra_processors: Optional[list[Processor]] = None,
    extra_context: Optional[dict] = None,
) -> None:
    """Configure structured logging with optional custom backend.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Output format - 'json' for structured, 'text' for console
        stream: Output stream (default: sys.stderr)
        service_name: Service name included in all log entries
        backend: Name of registered backend to use (e.g., "elk", "datadog")
        extra_processors: Additional structlog processors to include
        extra_context: Static context dict added to all log entries

    Example:
        # Basic configuration
        configure_logging(log_level="INFO", log_format="json")

        # With custom backend (after registering)
        register_backend("elk", ElkBackend("localhost", 5044))
        configure_logging(log_level="INFO", backend="elk")

        # With extra context
        configure_logging(
            log_level="INFO",
            service_name="weighing-parser-prod",
            extra_context={"environment": "production", "region": "kr-central"}
        )
    """
    global _current_config

    if stream is None:
        stream = sys.stderr

    # Store current configuration
    _current_config = LoggingConfig(
        log_level=log_level,
        log_format=log_format,
        stream=stream,
        service_name=service_name,
        backend=backend,
        extra_processors=extra_processors or [],
        extra_context=extra_context or {},
    )

    # Common processors for both formats
    common_processors: list[Processor] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        _create_service_context_processor(service_name, extra_context),
    ]

    # Add extra processors if provided
    if extra_processors:
        common_processors.extend(extra_processors)

    # Add backend-specific processors
    if backend and backend in _backends:
        backend_processors = _backends[backend].get_processors()
        common_processors.extend(backend_processors)

    if log_format == "json":
        # JSON format for production/log aggregation
        processors = common_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ]
    else:
        # Human-readable format for development
        processors = common_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    # Reset structlog configuration
    structlog.reset_defaults()

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,  # Disable caching for test flexibility
    )

    # Clear existing handlers from root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    # Configure handler based on backend or default
    if backend and backend in _backends:
        handler = _backends[backend].get_handler()
        formatter = _backends[backend].get_formatter()
        if formatter:
            handler.setFormatter(formatter)
        else:
            handler.setFormatter(logging.Formatter("%(message)s"))
    else:
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(message)s"))

    handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))


def get_logger(name: str = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Structured logger instance
    """
    return structlog.get_logger(name)


class ParserLogger:
    """Domain-specific logger with predefined event methods.

    Provides type-safe logging methods for common parser events.
    """

    def __init__(self, name: str = None):
        self._logger = get_logger(name)

    def parsing_started(
        self,
        file_path: str,
        file_count: int = 1,
        **extra
    ) -> None:
        """Log parsing start event."""
        self._logger.info(
            "parsing_started",
            file_path=file_path,
            file_count=file_count,
            **extra
        )

    def parsing_completed(
        self,
        file_path: str,
        duration_ms: float = None,
        success: bool = True,
        **extra
    ) -> None:
        """Log parsing completion event."""
        self._logger.info(
            "parsing_completed",
            file_path=file_path,
            duration_ms=duration_ms,
            success=success,
            **extra
        )

    def extraction_succeeded(
        self,
        field: str,
        value: str = None,
        confidence: float = None,
        **extra
    ) -> None:
        """Log successful field extraction."""
        self._logger.debug(
            "extraction_succeeded",
            field=field,
            value=value,
            confidence=confidence,
            **extra
        )

    def extraction_failed(
        self,
        field: str,
        error: str,
        **extra
    ) -> None:
        """Log failed field extraction."""
        self._logger.warning(
            "extraction_failed",
            field=field,
            error=error,
            **extra
        )

    def validation_error(
        self,
        error_type: str,
        message: str,
        **extra
    ) -> None:
        """Log validation error."""
        self._logger.warning(
            "validation_error",
            error_type=error_type,
            message=message,
            **extra
        )

    def parse_error(
        self,
        file_path: str,
        error: str,
        error_type: str = "ParserException",
        **extra
    ) -> None:
        """Log parse error."""
        self._logger.error(
            "parse_error",
            file_path=file_path,
            error=error,
            error_type=error_type,
            **extra
        )

    def batch_summary(
        self,
        total_files: int,
        successful: int,
        failed: int,
        with_warnings: int = 0,
        **extra
    ) -> None:
        """Log batch processing summary."""
        self._logger.info(
            "batch_summary",
            total_files=total_files,
            successful=successful,
            failed=failed,
            with_warnings=with_warnings,
            **extra
        )

    def info(self, event: str, **kwargs) -> None:
        """Generic info log."""
        self._logger.info(event, **kwargs)

    def warning(self, event: str, **kwargs) -> None:
        """Generic warning log."""
        self._logger.warning(event, **kwargs)

    def error(self, event: str, **kwargs) -> None:
        """Generic error log."""
        self._logger.error(event, **kwargs)

    def debug(self, event: str, **kwargs) -> None:
        """Generic debug log."""
        self._logger.debug(event, **kwargs)


# =============================================================================
# Pre-built Backend Implementations
# =============================================================================


class StreamBackend(LoggingBackend):
    """Simple stream-based backend for stdout/stderr/file logging.

    Example:
        # Log to file
        with open("app.log", "a") as f:
            register_backend("file", StreamBackend(stream=f))
            configure_logging(backend="file")
    """

    def __init__(self, stream: TextIO = None):
        """Initialize stream backend.

        Args:
            stream: Output stream (default: sys.stderr)
        """
        self.stream = stream or sys.stderr

    def get_handler(self) -> logging.Handler:
        return logging.StreamHandler(self.stream)


class HttpBackend(LoggingBackend):
    """HTTP-based backend for sending logs to REST endpoints.

    Compatible with:
    - Logstash HTTP input
    - Elasticsearch direct ingestion
    - Custom log aggregation APIs

    Example:
        register_backend("http", HttpBackend(
            url="http://logstash:8080",
            headers={"Authorization": "Bearer token"}
        ))
        configure_logging(backend="http")
    """

    def __init__(
        self,
        url: str,
        method: str = "POST",
        headers: Optional[dict] = None,
        timeout: float = 5.0,
    ):
        """Initialize HTTP backend.

        Args:
            url: Target URL for log ingestion
            method: HTTP method (default: POST)
            headers: Additional HTTP headers
            timeout: Request timeout in seconds
        """
        self.url = url
        self.method = method
        self.headers = headers or {}
        self.timeout = timeout

    def get_handler(self) -> logging.Handler:
        """Return an HTTP handler.

        Note: Requires implementation of HTTPHandler or use of
        third-party packages like python-logstash-async.
        """
        # Return a placeholder handler - users should override with actual HTTP handler
        import logging.handlers

        # Using MemoryHandler as placeholder - actual implementation would use
        # python-logstash, logstash_async, or custom HTTPHandler
        handler = logging.handlers.MemoryHandler(capacity=100)
        return handler


class SocketBackend(LoggingBackend):
    """TCP/UDP socket backend for Logstash, syslog, etc.

    Example:
        # For Logstash TCP input
        register_backend("logstash", SocketBackend(
            host="logstash.example.com",
            port=5044,
            protocol="tcp"
        ))
        configure_logging(backend="logstash")
    """

    def __init__(
        self,
        host: str,
        port: int,
        protocol: str = "tcp",
    ):
        """Initialize socket backend.

        Args:
            host: Target host address
            port: Target port number
            protocol: 'tcp' or 'udp'
        """
        self.host = host
        self.port = port
        self.protocol = protocol.lower()

    def get_handler(self) -> logging.Handler:
        """Return a socket handler."""
        import logging.handlers

        if self.protocol == "udp":
            return logging.handlers.DatagramHandler(self.host, self.port)
        else:
            return logging.handlers.SocketHandler(self.host, self.port)


# =============================================================================
# Convenience Functions
# =============================================================================


def configure_for_elk(
    host: str,
    port: int = 5044,
    log_level: str = "INFO",
    service_name: str = "weighing-parser",
    extra_context: Optional[dict] = None,
) -> None:
    """Convenience function to configure logging for ELK Stack.

    Sets up TCP socket logging to Logstash.

    Args:
        host: Logstash host address
        port: Logstash TCP input port (default: 5044)
        log_level: Logging level
        service_name: Service name in logs
        extra_context: Additional context fields

    Example:
        configure_for_elk(
            host="logstash.example.com",
            port=5044,
            extra_context={"environment": "production"}
        )
    """
    register_backend("elk", SocketBackend(host=host, port=port, protocol="tcp"))
    configure_logging(
        log_level=log_level,
        log_format="json",
        service_name=service_name,
        backend="elk",
        extra_context=extra_context,
    )


def configure_for_file(
    file_path: str,
    log_level: str = "INFO",
    log_format: str = "json",
    service_name: str = "weighing-parser",
) -> None:
    """Convenience function to configure file-based logging.

    Args:
        file_path: Path to log file
        log_level: Logging level
        log_format: 'json' or 'text'
        service_name: Service name in logs

    Example:
        configure_for_file("/var/log/weighing-parser/app.log")
    """
    file_handler = logging.FileHandler(file_path, encoding="utf-8")

    class FileBackend(LoggingBackend):
        def get_handler(self) -> logging.Handler:
            return file_handler

    register_backend("file", FileBackend())
    configure_logging(
        log_level=log_level,
        log_format=log_format,
        service_name=service_name,
        backend="file",
    )
