"""
Korean Vehicle Weighing Receipt OCR Parser (계근지 파서)

A Python library for parsing OCR-extracted text from Korean vehicle weighing receipts.
"""

from .parser import WeighingReceiptParser
from .models.receipt import WeighingReceipt
from .exceptions import (
    ParserException,
    InvalidOCRFormatError,
    EmptyDocumentError,
    JSONParseError,
    MissingRequiredFieldError,
    ExtractionError,
    FieldNotFoundError,
    ValidationError,
    WeightValidationError,
)
from .logging import (
    configure_logging,
    get_logger,
    ParserLogger,
    LoggingBackend,
    LoggingConfig,
    register_backend,
    unregister_backend,
    get_registered_backends,
    get_current_config,
    configure_for_elk,
    configure_for_file,
    StreamBackend,
    HttpBackend,
    SocketBackend,
)

__version__ = "1.1.0"
__all__ = [
    "WeighingReceiptParser",
    "WeighingReceipt",
    # Exceptions
    "ParserException",
    "InvalidOCRFormatError",
    "EmptyDocumentError",
    "JSONParseError",
    "MissingRequiredFieldError",
    "ExtractionError",
    "FieldNotFoundError",
    "ValidationError",
    "WeightValidationError",
    # Logging
    "configure_logging",
    "get_logger",
    "ParserLogger",
    "LoggingBackend",
    "LoggingConfig",
    "register_backend",
    "unregister_backend",
    "get_registered_backends",
    "get_current_config",
    "configure_for_elk",
    "configure_for_file",
    "StreamBackend",
    "HttpBackend",
    "SocketBackend",
]
