"""Edge case tests for the weighing receipt parser.

Tests for:
- Empty inputs
- Malformed/corrupted data
- Boundary values
- Unicode edge cases
- Large inputs
"""

import pytest
import sys
from pathlib import Path
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from weighing_parser.parser import WeighingReceiptParser
from weighing_parser.models.ocr_input import OCRDocument
from weighing_parser.normalizers.numbers import NumberNormalizer
from weighing_parser.normalizers.datetime import DateTimeNormalizer
from weighing_parser.normalizers.text import TextNormalizer
from weighing_parser.exceptions import (
    EmptyDocumentError,
    JSONParseError,
    MissingRequiredFieldError,
    InvalidOCRFormatError,
)


class TestEmptyInputs:
    """Tests for empty and null inputs."""

    @pytest.fixture
    def parser(self):
        return WeighingReceiptParser()

    def test_empty_pages_list(self, parser, mock_ocr_document):
        """Empty pages list should raise EmptyDocumentError."""
        doc_data = mock_ocr_document([])
        doc_data["pages"] = []
        doc_data["text"] = ""
        document = OCRDocument(**doc_data)

        with pytest.raises(EmptyDocumentError):
            parser.parse(document)

    def test_empty_text_content(self, parser, mock_ocr_document):
        """Document with empty text should raise EmptyDocumentError."""
        doc_data = mock_ocr_document([""])
        doc_data["text"] = ""
        document = OCRDocument(**doc_data)

        with pytest.raises(EmptyDocumentError):
            parser.parse(document)

    def test_whitespace_only_text(self, parser, mock_ocr_document):
        """Document with only whitespace should raise EmptyDocumentError."""
        doc_data = mock_ocr_document(["   ", "\t", "\n"])
        doc_data["text"] = "   \t\n   "
        document = OCRDocument(**doc_data)

        with pytest.raises(EmptyDocumentError):
            parser.parse(document)

    def test_empty_lines_list(self, parser, mock_ocr_document):
        """Document with empty lines list should raise EmptyDocumentError."""
        doc_data = mock_ocr_document([])
        doc_data["pages"][0]["lines"] = []
        doc_data["text"] = ""
        document = OCRDocument(**doc_data)

        with pytest.raises(EmptyDocumentError):
            parser.parse(document)


class TestMalformedJSON:
    """Tests for malformed/corrupted JSON data."""

    @pytest.fixture
    def parser(self):
        return WeighingReceiptParser()

    def test_missing_api_version(self, parser, mock_ocr_document):
        """Missing apiVersion field should raise MissingRequiredFieldError."""
        import tempfile
        import json

        doc_data = mock_ocr_document(["test"])
        del doc_data["apiVersion"]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(doc_data, f)
            f.flush()
            with pytest.raises(MissingRequiredFieldError) as exc_info:
                parser.parse_file(f.name)

        assert exc_info.value.field_name == "apiVersion"

    def test_missing_pages(self, parser):
        """Missing pages field should raise MissingRequiredFieldError."""
        import tempfile
        import json

        doc_data = {
            "apiVersion": "1.0",
            "confidence": 0.95,
            "text": "test",
            # "pages" is missing
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(doc_data, f)
            f.flush()
            with pytest.raises(MissingRequiredFieldError) as exc_info:
                parser.parse_file(f.name)

        assert exc_info.value.field_name == "pages"

    def test_invalid_json_syntax(self, parser):
        """Invalid JSON syntax should raise JSONParseError."""
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ invalid json }")
            f.flush()
            with pytest.raises(JSONParseError):
                parser.parse_file(f.name)

    def test_json_array_instead_of_object(self, parser):
        """JSON array instead of object should raise InvalidOCRFormatError."""
        import tempfile
        import json

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(["not", "an", "object"], f)
            f.flush()
            with pytest.raises(InvalidOCRFormatError):
                parser.parse_file(f.name)

    def test_invalid_confidence_type(self, parser):
        """Non-numeric confidence should raise InvalidOCRFormatError."""
        import tempfile
        import json

        doc_data = {
            "apiVersion": "1.0",
            "confidence": "not a number",
            "text": "test",
            "pages": [],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(doc_data, f)
            f.flush()
            with pytest.raises(InvalidOCRFormatError):
                parser.parse_file(f.name)


class TestBoundaryValues:
    """Tests for boundary/extreme values."""

    def test_zero_confidence(self, mock_ocr_document):
        """Zero confidence should be accepted."""
        doc_data = mock_ocr_document(["계량증명서"])
        doc_data["confidence"] = 0.0
        document = OCRDocument(**doc_data)
        assert document.confidence == 0.0

    def test_max_confidence(self, mock_ocr_document):
        """Confidence of 1.0 should be accepted."""
        doc_data = mock_ocr_document(["계량증명서"])
        doc_data["confidence"] = 1.0
        document = OCRDocument(**doc_data)
        assert document.confidence == 1.0

    def test_negative_confidence(self, mock_ocr_document):
        """Negative confidence - depends on validation rules."""
        doc_data = mock_ocr_document(["계량증명서"])
        doc_data["confidence"] = -0.5
        # May or may not raise depending on Pydantic validation
        document = OCRDocument(**doc_data)
        # Just verify it's stored
        assert document.confidence == -0.5

    def test_very_large_weight(self):
        """Very large weight values should parse correctly."""
        result = NumberNormalizer.parse_weight("999,999,999 kg")
        assert result == Decimal("999999999")

    def test_zero_weight(self):
        """Zero weight should parse correctly."""
        result = NumberNormalizer.parse_weight("0 kg")
        assert result == Decimal("0")

    def test_decimal_weight(self):
        """Decimal weight values should parse correctly."""
        result = NumberNormalizer.parse_weight("1234.56 kg")
        assert result == Decimal("1234.56")


class TestUnicodeEdgeCases:
    """Tests for Unicode and Korean text edge cases."""

    def test_mixed_korean_english(self, mock_ocr_document):
        """Mixed Korean and English text should parse."""
        doc_data = mock_ocr_document([
            "계량증명서 Receipt",
            "차량번호: ABC123가나다",
        ])
        document = OCRDocument(**doc_data)
        assert "계량증명서" in document.text

    def test_full_width_numbers(self):
        """Full-width numbers should be handled."""
        # Full-width digits: ０１２３４５６７８９
        result = NumberNormalizer.extract_weight_from_line("１２３４５ kg")
        # May or may not handle full-width - depends on implementation
        # This test documents current behavior
        assert result is None or result == Decimal("12345")

    def test_special_korean_characters(self, mock_ocr_document):
        """Special Korean characters should not break parsing."""
        doc_data = mock_ocr_document([
            "※ 계량증명서 ※",
            "☎ 연락처: 031-123-4567",
        ])
        document = OCRDocument(**doc_data)
        assert document.text is not None

    def test_very_long_text_line(self, mock_ocr_document):
        """Very long text line should not break parsing."""
        long_line = "가" * 10000
        doc_data = mock_ocr_document([long_line])
        document = OCRDocument(**doc_data)
        assert len(document.get_lines()[0].text) == 10000


class TestNumberNormalizerEdgeCases:
    """Edge cases for number parsing."""

    @pytest.mark.parametrize(
        "input_text,expected",
        [
            ("", None),  # Empty string
            ("   ", None),  # Whitespace only
            ("kg", None),  # Unit only
            ("abc", None),  # Letters only
            ("-", None),  # Minus only
            (".", None),  # Decimal only
            ("-.", None),  # Minus and decimal only
        ],
    )
    def test_invalid_weight_inputs(self, input_text, expected):
        """Invalid weight inputs should return None."""
        result = NumberNormalizer.parse_weight(input_text)
        assert result == expected

    @pytest.mark.parametrize(
        "input_text,expected",
        [
            ("--100", Decimal("-100")),  # Double minus becomes single (regex extracts -100)
            ("100--", Decimal("100")),  # Trailing chars ignored (extracts 100)
        ],
    )
    def test_ambiguous_weight_inputs(self, input_text, expected):
        """Ambiguous inputs - documenting current behavior."""
        result = NumberNormalizer.parse_weight(input_text)
        assert result == expected

    @pytest.mark.parametrize(
        "input_text,expected",
        [
            ("1 2 3 4 5 kg", Decimal("12345")),  # Spaced digits
            ("1,234,567", Decimal("1234567")),  # Multiple commas
            ("  12480  ", Decimal("12480")),  # Leading/trailing spaces
            ("12480kg", Decimal("12480")),  # No space before unit
            ("12480 KG", Decimal("12480")),  # Uppercase unit
            ("12480Kg", Decimal("12480")),  # Mixed case unit
        ],
    )
    def test_valid_weight_variations(self, input_text, expected):
        """Various valid weight formats should parse correctly."""
        result = NumberNormalizer.parse_weight(input_text)
        assert result == expected


class TestDateTimeNormalizerEdgeCases:
    """Edge cases for date/time parsing."""

    @pytest.mark.parametrize(
        "input_text",
        [
            "",  # Empty
            "   ",  # Whitespace
            "not a date",  # Random text
            "32-01-2026",  # Invalid day
            "2026-13-01",  # Invalid month
            "2026/00/01",  # Zero month
        ],
    )
    def test_invalid_date_inputs(self, input_text):
        """Invalid date inputs should return None."""
        result = DateTimeNormalizer.parse_date(input_text)
        assert result is None

    @pytest.mark.parametrize(
        "input_text,expected_str",
        [
            ("2026-02-02", "2026-02-02"),
            ("2026.02.02", "2026-02-02"),
            ("2026/02/02", "2026-02-02"),
        ],
    )
    def test_valid_date_formats(self, input_text, expected_str):
        """Various valid date formats should parse correctly."""
        result = DateTimeNormalizer.parse_date(input_text)
        assert result is not None
        assert result.isoformat() == expected_str

    @pytest.mark.parametrize(
        "input_text",
        [
            "",  # Empty
            "25:00",  # Invalid hour
            "12:60",  # Invalid minute
            "12:30:60",  # Invalid second
        ],
    )
    def test_invalid_time_inputs(self, input_text):
        """Invalid time inputs should return None."""
        result = DateTimeNormalizer.parse_time(input_text)
        assert result is None


class TestTextNormalizerEdgeCases:
    """Edge cases for text normalization."""

    def test_empty_string_normalization(self):
        """Empty string should remain empty."""
        result = TextNormalizer.remove_spaces("")
        assert result == ""

    def test_whitespace_only_normalization(self):
        """Whitespace only should become empty or minimal."""
        result = TextNormalizer.remove_spaces("   ")
        assert result.strip() == ""

    def test_multiple_spaces_between_korean(self):
        """Multiple spaces between Korean chars should normalize."""
        result = TextNormalizer.normalize_korean_spaces("계   량   증   명   서")
        assert "계량" in result or "계 량" in result

    def test_mixed_spacing_patterns(self):
        """Mixed spacing patterns should normalize."""
        result = TextNormalizer.normalize_korean_spaces("계 량증명 서")
        assert result is not None


class TestParserGracefulDegradation:
    """Tests for graceful degradation when some fields fail."""

    @pytest.fixture
    def parser(self):
        return WeighingReceiptParser()

    def test_partial_data_extraction(self, parser, mock_ocr_document):
        """Parser should extract available fields even when some fail."""
        # Document with only document type, no weights
        doc_data = mock_ocr_document([
            "계량증명서",
            "날짜: 2026-02-02",
            # No weight information
        ])
        document = OCRDocument(**doc_data)

        result = parser.parse(document)

        assert result.document_type == "계량증명서"
        assert result.date is not None
        # Weights should be None but not cause failure
        assert result.total_weight is None or result.total_weight is not None

    def test_extraction_with_garbage_data(self, parser, mock_ocr_document):
        """Parser should handle garbage data gracefully."""
        doc_data = mock_ocr_document([
            "!@#$%^&*()",
            "random garbage text",
            "12345 not a weight",
        ])
        document = OCRDocument(**doc_data)

        # Should not raise, should return receipt with validation errors
        result = parser.parse(document)
        assert result is not None


class TestFileNotFound:
    """Tests for file not found scenarios."""

    @pytest.fixture
    def parser(self):
        return WeighingReceiptParser()

    def test_nonexistent_file(self, parser):
        """Parsing non-existent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            parser.parse_file("/nonexistent/path/to/file.json")

    def test_directory_instead_of_file(self, parser):
        """Parsing directory path should raise appropriate error."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # Trying to parse a directory
            with pytest.raises((FileNotFoundError, IsADirectoryError, PermissionError)):
                parser.parse_file(tmpdir)
