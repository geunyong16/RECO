"""Unit tests for custom exception classes."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from weighing_parser.exceptions import (
    ParserException,
    InvalidOCRFormatError,
    EmptyDocumentError,
    JSONParseError,
    MissingRequiredFieldError,
    ExtractionError,
    FieldNotFoundError,
    InvalidFieldValueError,
    LowConfidenceError,
    ValidationError,
    WeightValidationError,
    WeightEquationError,
    NegativeWeightError,
    WeightOrderError,
    NormalizationError,
    DateParseError,
    WeightParseError,
    OutputError,
    FileWriteError,
    UnsupportedFormatError,
)


class TestParserException:
    """Tests for base ParserException."""

    def test_basic_message(self):
        """Exception should store message."""
        exc = ParserException("Test error")
        assert exc.message == "Test error"
        assert str(exc) == "Test error"

    def test_with_details(self):
        """Exception should include details in string."""
        exc = ParserException("Test error", {"key": "value"})
        assert exc.details == {"key": "value"}
        assert "key" in str(exc)
        assert "value" in str(exc)

    def test_empty_details(self):
        """Exception with no details should work."""
        exc = ParserException("Test error")
        assert exc.details == {}


class TestInvalidOCRFormatError:
    """Tests for InvalidOCRFormatError."""

    def test_with_filepath(self):
        """Should include filepath in details."""
        exc = InvalidOCRFormatError("Invalid format", filepath="/path/to/file.json")
        assert exc.filepath == "/path/to/file.json"
        assert exc.details["filepath"] == "/path/to/file.json"

    def test_without_filepath(self):
        """Should work without filepath."""
        exc = InvalidOCRFormatError("Invalid format")
        assert exc.filepath is None


class TestEmptyDocumentError:
    """Tests for EmptyDocumentError."""

    def test_default_message(self):
        """Should have default message."""
        exc = EmptyDocumentError()
        assert "no pages" in exc.message.lower() or "content" in exc.message.lower()

    def test_with_filepath(self):
        """Should include filepath if provided."""
        exc = EmptyDocumentError(filepath="/path/file.json")
        assert exc.filepath == "/path/file.json"


class TestJSONParseError:
    """Tests for JSONParseError."""

    def test_includes_original_error(self):
        """Should include original JSON error."""
        exc = JSONParseError("Expecting property name", filepath="test.json")
        assert "Expecting property name" in exc.message
        assert exc.details["json_error"] == "Expecting property name"


class TestMissingRequiredFieldError:
    """Tests for MissingRequiredFieldError."""

    def test_field_name_stored(self):
        """Should store field name."""
        exc = MissingRequiredFieldError("apiVersion")
        assert exc.field_name == "apiVersion"
        assert "apiVersion" in exc.message


class TestExtractionError:
    """Tests for ExtractionError and subclasses."""

    def test_field_not_found(self):
        """FieldNotFoundError should store patterns."""
        exc = FieldNotFoundError("vehicle_number", ["차량번호", "차번호"])
        assert exc.field_name == "vehicle_number"
        assert exc.searched_patterns == ["차량번호", "차번호"]

    def test_invalid_field_value(self):
        """InvalidFieldValueError should store value and reason."""
        exc = InvalidFieldValueError("weight", "-100", "negative not allowed")
        assert exc.field_name == "weight"
        assert exc.value == "-100"
        assert exc.reason == "negative not allowed"

    def test_low_confidence(self):
        """LowConfidenceError should store confidence values."""
        exc = LowConfidenceError("document_type", 0.3, 0.5)
        assert exc.field_name == "document_type"
        assert exc.confidence == 0.3
        assert exc.threshold == 0.5


class TestWeightValidationError:
    """Tests for weight validation errors."""

    def test_weight_equation_error(self):
        """WeightEquationError should calculate difference."""
        exc = WeightEquationError(
            total=12480, tare=7470, net=5100, expected_net=5010, tolerance=10
        )
        assert exc.expected_net == 5010
        assert exc.difference == 90  # |5100 - 5010|

    def test_negative_weight_error(self):
        """NegativeWeightError should store weight type."""
        exc = NegativeWeightError("tare_weight", -100)
        assert exc.weight_type == "tare_weight"
        assert exc.value == -100

    def test_weight_order_error(self):
        """WeightOrderError should indicate order issue."""
        exc = WeightOrderError(total=5000, tare=7000)
        assert "tare" in exc.message.lower()
        assert "total" in exc.message.lower()


class TestNormalizationError:
    """Tests for normalization errors."""

    def test_date_parse_error(self):
        """DateParseError should store input value."""
        exc = DateParseError("invalid-date")
        assert exc.input_value == "invalid-date"

    def test_date_parse_error_with_formats(self):
        """DateParseError should store supported formats."""
        exc = DateParseError("invalid", ["YYYY-MM-DD", "YYYY.MM.DD"])
        assert exc.details["supported_formats"] == ["YYYY-MM-DD", "YYYY.MM.DD"]

    def test_weight_parse_error(self):
        """WeightParseError should store input value."""
        exc = WeightParseError("not-a-weight")
        assert exc.input_value == "not-a-weight"


class TestOutputError:
    """Tests for output errors."""

    def test_file_write_error(self):
        """FileWriteError should store filepath."""
        exc = FileWriteError("/path/output.json", "Permission denied")
        assert exc.filepath == "/path/output.json"
        assert "Permission denied" in exc.details["error"]

    def test_unsupported_format_error(self):
        """UnsupportedFormatError should list supported formats."""
        exc = UnsupportedFormatError("xml", ["json", "csv"])
        assert exc.format_name == "xml"
        assert exc.supported_formats == ["json", "csv"]


class TestExceptionHierarchy:
    """Tests for exception inheritance hierarchy."""

    def test_all_inherit_from_parser_exception(self):
        """All custom exceptions should inherit from ParserException."""
        exceptions = [
            InvalidOCRFormatError("test"),
            EmptyDocumentError(),
            JSONParseError("test"),
            MissingRequiredFieldError("test"),
            ExtractionError("field", "message"),
            FieldNotFoundError("field"),
            ValidationError("test"),
            WeightValidationError("test"),
            NormalizationError("input", "message"),
            OutputError("test"),
        ]

        for exc in exceptions:
            assert isinstance(exc, ParserException)

    def test_can_catch_by_base_class(self):
        """Should be able to catch by base class."""
        with pytest.raises(ParserException):
            raise EmptyDocumentError()

        with pytest.raises(InvalidOCRFormatError):
            raise JSONParseError("test")

        with pytest.raises(ValidationError):
            raise WeightValidationError("test")
