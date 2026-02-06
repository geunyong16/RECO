"""Unit tests for normalizer modules."""

import pytest
from datetime import date, time
from decimal import Decimal

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from weighing_parser.normalizers.text import TextNormalizer
from weighing_parser.normalizers.numbers import NumberNormalizer
from weighing_parser.normalizers.datetime import DateTimeNormalizer


class TestTextNormalizer:
    """Tests for TextNormalizer."""

    @pytest.mark.parametrize(
        "input_text,expected",
        [
            ("계 량 증 명 서", "계량증명서"),
            ("계량증명서", "계량증명서"),
            ("차 량 번 호", "차량번호"),
            ("총 중 량", "총중량"),
            ("실 중 량", "실중량"),
        ],
    )
    def test_remove_spaces(self, input_text, expected):
        """Test space removal from Korean text."""
        assert TextNormalizer.remove_spaces(input_text) == expected

    @pytest.mark.parametrize(
        "input_text,expected",
        [
            ("계 그 표", "계표"),
            ("계그표", "계표"),
        ],
    )
    def test_fix_ocr_errors(self, input_text, expected):
        """Test OCR error correction."""
        result = TextNormalizer.fix_ocr_errors(input_text)
        assert TextNormalizer.remove_spaces(result) == expected

    @pytest.mark.parametrize(
        "input_text,expected",
        [
            ("차량번호: 8713", "8713"),
            ("계량일자: 2026-02-02", "2026-02-02"),
            ("거래처: 고요환경", "고요환경"),
            ("no colon here", None),
        ],
    )
    def test_extract_after_colon(self, input_text, expected):
        """Test value extraction after colon."""
        assert TextNormalizer.extract_after_colon(input_text) == expected


class TestNumberNormalizer:
    """Tests for NumberNormalizer with Decimal support."""

    @pytest.mark.parametrize(
        "input_str,expected",
        [
            ("12,480", Decimal("12480")),
            ("5,010", Decimal("5010")),
            ("7,470", Decimal("7470")),
            ("5 900", Decimal("5900")),
            ("13 460", Decimal("13460")),
            ("7 560", Decimal("7560")),
            ("130", Decimal("130")),
            ("14,230", Decimal("14230")),
            ("12,910 kg", Decimal("12910")),
            ("1,320 kg", Decimal("1320")),
        ],
    )
    def test_parse_weight(self, input_str, expected):
        """Test weight parsing returns Decimal from various formats."""
        result = NumberNormalizer.parse_weight(input_str)
        assert result == expected
        assert isinstance(result, Decimal)

    def test_parse_weight_precision(self):
        """Test that Decimal preserves precision without floating point errors."""
        result = NumberNormalizer.parse_weight("12480")
        assert result == Decimal("12480")
        # Verify no floating point issues
        assert str(result) == "12480"

    @pytest.mark.parametrize(
        "input_str",
        [
            "",
            "abc",
            "no numbers",
        ],
    )
    def test_parse_weight_invalid(self, input_str):
        """Test weight parsing with invalid input."""
        assert NumberNormalizer.parse_weight(input_str) is None

    @pytest.mark.parametrize(
        "input_str,expected",
        [
            ("37.105317", 37.105317),
            ("127.375673", 127.375673),
            ("invalid", None),
        ],
    )
    def test_parse_decimal(self, input_str, expected):
        """Test decimal number parsing (for GPS coordinates)."""
        result = NumberNormalizer.parse_decimal(input_str)
        if expected is None:
            assert result is None
        else:
            assert result == pytest.approx(expected)

    @pytest.mark.parametrize(
        "input_str,expected",
        [
            ("05:26:18 12,480 kg", Decimal("12480")),
            ("13 460 kg", Decimal("13460")),
            ("실중량: 5,010 kg", Decimal("5010")),
        ],
    )
    def test_extract_weight_from_line(self, input_str, expected):
        """Test weight extraction from full line returns Decimal."""
        result = NumberNormalizer.extract_weight_from_line(input_str)
        assert result == expected
        assert isinstance(result, Decimal)


class TestDateTimeNormalizer:
    """Tests for DateTimeNormalizer."""

    @pytest.mark.parametrize(
        "input_str,expected",
        [
            ("2026-02-02", date(2026, 2, 2)),
            ("2025-12-01", date(2025, 12, 1)),
            ("계량일자: 2026-02-01", date(2026, 2, 1)),
            ("no date here", None),
        ],
    )
    def test_parse_date(self, input_str, expected):
        """Test date parsing from various formats."""
        assert DateTimeNormalizer.parse_date(input_str) == expected

    @pytest.mark.parametrize(
        "input_str,expected",
        [
            ("05:26:18", time(5, 26, 18)),
            ("02:07", time(2, 7, 0)),
            ("11시 33분", time(11, 33, 0)),
            ("(09:09)", time(9, 9, 0)),
        ],
    )
    def test_parse_time(self, input_str, expected):
        """Test time parsing from various formats."""
        assert DateTimeNormalizer.parse_time(input_str) == expected

    @pytest.mark.parametrize(
        "input_str,expected_date,expected_seq",
        [
            ("2026-02-02-00004", date(2026, 2, 2), "00004"),
            ("2026-02-02 0016", date(2026, 2, 2), "0016"),
            ("2026-02-02", date(2026, 2, 2), None),
        ],
    )
    def test_parse_date_with_sequence(self, input_str, expected_date, expected_seq):
        """Test date and sequence number parsing."""
        parsed_date, sequence = DateTimeNormalizer.parse_date_with_sequence(input_str)
        assert parsed_date == expected_date
        assert sequence == expected_seq

    @pytest.mark.parametrize(
        "input_str,expected",
        [
            ("2026-02-02 05:37:55", "2026-02-02 05:37:55"),
            ("timestamp: 2026-02-01 11:55:35", "2026-02-01 11:55:35"),
        ],
    )
    def test_parse_timestamp(self, input_str, expected):
        """Test full timestamp parsing."""
        assert DateTimeNormalizer.parse_timestamp(input_str) == expected
