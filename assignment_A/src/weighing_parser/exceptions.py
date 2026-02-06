"""Custom exceptions for the weighing receipt parser.

This module provides a hierarchy of specific exceptions for better error handling
and debugging. Each exception type represents a distinct error category.
"""

from typing import Optional, Any


class ParserException(Exception):
    """Base exception for all parser errors.

    Attributes:
        message: Human-readable error description
        details: Additional context for debugging
    """

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (details: {self.details})"
        return self.message


# =============================================================================
# Input/Format Errors
# =============================================================================

class InvalidOCRFormatError(ParserException):
    """Raised when OCR JSON format is invalid or malformed."""

    def __init__(self, message: str, filepath: Optional[str] = None,
                 details: Optional[dict[str, Any]] = None):
        details = details or {}
        if filepath:
            details["filepath"] = filepath
        super().__init__(message, details)
        self.filepath = filepath


class EmptyDocumentError(InvalidOCRFormatError):
    """Raised when document has no pages or content."""

    def __init__(self, filepath: Optional[str] = None):
        super().__init__(
            "Document has no pages or content",
            filepath=filepath,
            details={"error_type": "empty_document"}
        )


class MissingRequiredFieldError(InvalidOCRFormatError):
    """Raised when a required field is missing from OCR JSON."""

    def __init__(self, field_name: str, filepath: Optional[str] = None):
        super().__init__(
            f"Missing required field: {field_name}",
            filepath=filepath,
            details={"missing_field": field_name}
        )
        self.field_name = field_name


class JSONParseError(InvalidOCRFormatError):
    """Raised when JSON parsing fails."""

    def __init__(self, original_error: str, filepath: Optional[str] = None):
        super().__init__(
            f"Invalid JSON format: {original_error}",
            filepath=filepath,
            details={"json_error": original_error}
        )


# =============================================================================
# Extraction Errors
# =============================================================================

class ExtractionError(ParserException):
    """Base class for extraction-related errors."""

    def __init__(self, field_name: str, message: str,
                 details: Optional[dict[str, Any]] = None):
        details = details or {}
        details["field_name"] = field_name
        super().__init__(message, details)
        self.field_name = field_name


class FieldNotFoundError(ExtractionError):
    """Raised when a field cannot be found in the document."""

    def __init__(self, field_name: str, searched_patterns: Optional[list[str]] = None):
        details = {}
        if searched_patterns:
            details["searched_patterns"] = searched_patterns
        super().__init__(
            field_name,
            f"Could not find field '{field_name}' in document",
            details
        )
        self.searched_patterns = searched_patterns


class InvalidFieldValueError(ExtractionError):
    """Raised when an extracted field value is invalid."""

    def __init__(self, field_name: str, value: Any, reason: str):
        super().__init__(
            field_name,
            f"Invalid value for '{field_name}': {value} ({reason})",
            {"invalid_value": str(value), "reason": reason}
        )
        self.value = value
        self.reason = reason


class LowConfidenceError(ExtractionError):
    """Raised when extraction confidence is below threshold."""

    def __init__(self, field_name: str, confidence: float, threshold: float):
        super().__init__(
            field_name,
            f"Low confidence for '{field_name}': {confidence:.2%} < {threshold:.2%}",
            {"confidence": confidence, "threshold": threshold}
        )
        self.confidence = confidence
        self.threshold = threshold


# =============================================================================
# Validation Errors
# =============================================================================

class ValidationError(ParserException):
    """Base class for validation errors."""
    pass


class WeightValidationError(ValidationError):
    """Raised when weight validation fails."""

    def __init__(self, message: str, total: Optional[float] = None,
                 tare: Optional[float] = None, net: Optional[float] = None,
                 tolerance: Optional[float] = None):
        details = {}
        if total is not None:
            details["total_weight"] = total
        if tare is not None:
            details["tare_weight"] = tare
        if net is not None:
            details["net_weight"] = net
        if tolerance is not None:
            details["tolerance_kg"] = tolerance
        super().__init__(message, details)


class WeightEquationError(WeightValidationError):
    """Raised when weight equation (net = total - tare) doesn't balance."""

    def __init__(self, total: float, tare: float, net: float,
                 expected_net: float, tolerance: float):
        difference = abs(net - expected_net)
        super().__init__(
            f"Weight equation mismatch: expected net={expected_net}kg, "
            f"got {net}kg (diff={difference}kg, tolerance={tolerance}kg)",
            total=total,
            tare=tare,
            net=net,
            tolerance=tolerance
        )
        self.expected_net = expected_net
        self.difference = difference


class NegativeWeightError(WeightValidationError):
    """Raised when a weight value is negative."""

    def __init__(self, weight_type: str, value: float):
        super().__init__(
            f"Negative weight not allowed: {weight_type}={value}kg"
        )
        self.weight_type = weight_type
        self.value = value


class WeightOrderError(WeightValidationError):
    """Raised when weight order is invalid (e.g., tare > total)."""

    def __init__(self, total: float, tare: float):
        super().__init__(
            f"Invalid weight order: tare ({tare}kg) > total ({total}kg)",
            total=total,
            tare=tare
        )


# =============================================================================
# Normalization Errors
# =============================================================================

class NormalizationError(ParserException):
    """Base class for normalization errors."""

    def __init__(self, input_value: str, message: str,
                 details: Optional[dict[str, Any]] = None):
        details = details or {}
        details["input_value"] = input_value
        super().__init__(message, details)
        self.input_value = input_value


class DateParseError(NormalizationError):
    """Raised when date parsing fails."""

    def __init__(self, input_value: str, supported_formats: Optional[list[str]] = None):
        details = {}
        if supported_formats:
            details["supported_formats"] = supported_formats
        super().__init__(
            input_value,
            f"Could not parse date from: '{input_value}'",
            details
        )


class WeightParseError(NormalizationError):
    """Raised when weight parsing fails."""

    def __init__(self, input_value: str):
        super().__init__(
            input_value,
            f"Could not parse weight from: '{input_value}'"
        )


class TimeParseError(NormalizationError):
    """Raised when time parsing fails."""

    def __init__(self, input_value: str):
        super().__init__(
            input_value,
            f"Could not parse time from: '{input_value}'"
        )


# =============================================================================
# Output Errors
# =============================================================================

class OutputError(ParserException):
    """Base class for output-related errors."""
    pass


class FileWriteError(OutputError):
    """Raised when file writing fails."""

    def __init__(self, filepath: str, original_error: str):
        super().__init__(
            f"Failed to write file: {filepath}",
            {"filepath": filepath, "error": original_error}
        )
        self.filepath = filepath


class UnsupportedFormatError(OutputError):
    """Raised when output format is not supported."""

    def __init__(self, format_name: str, supported_formats: list[str]):
        super().__init__(
            f"Unsupported output format: '{format_name}'",
            {"format": format_name, "supported": supported_formats}
        )
        self.format_name = format_name
        self.supported_formats = supported_formats
