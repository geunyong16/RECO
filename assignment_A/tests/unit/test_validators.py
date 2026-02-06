"""Unit tests for validator modules."""

import pytest
import warnings
from decimal import Decimal

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from weighing_parser.validators.weights import WeightValidator
from weighing_parser.validators.confidence import ConfidenceValidator


class TestWeightValidator:
    """Tests for WeightValidator (deprecated class with Decimal support)."""

    @pytest.fixture
    def validator(self):
        # Suppress deprecation warning for test fixture
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            return WeightValidator(tolerance_kg=Decimal("10"))

    def test_deprecation_warning(self):
        """Test that WeightValidator shows deprecation warning."""
        with pytest.warns(DeprecationWarning, match="deprecated"):
            WeightValidator()

    @pytest.mark.parametrize(
        "total,tare,net",
        [
            (Decimal("12480"), Decimal("7470"), Decimal("5010")),  # Sample 01
            (Decimal("13460"), Decimal("7560"), Decimal("5900")),  # Sample 02
            (Decimal("14080"), Decimal("13950"), Decimal("130")),  # Sample 03
            (Decimal("14230"), Decimal("12910"), Decimal("1320")),  # Sample 04
        ],
    )
    def test_valid_weight_equation(self, validator, total, tare, net):
        """Test valid weight equations from sample data with Decimal."""
        is_valid, error = validator.validate_weight_equation(total, tare, net)
        assert is_valid
        assert error is None

    def test_valid_weight_equation_with_int(self, validator):
        """Test that validator still accepts int values for backward compatibility."""
        is_valid, error = validator.validate_weight_equation(12480, 7470, 5010)
        assert is_valid
        assert error is None

    def test_invalid_weight_equation(self, validator):
        """Test invalid weight equation detection."""
        is_valid, error = validator.validate_weight_equation(
            Decimal("10000"), Decimal("5000"), Decimal("4000")
        )
        assert not is_valid
        assert "mismatch" in error.lower()

    def test_weight_equation_within_tolerance(self, validator):
        """Test weight equation within tolerance."""
        # 10000 - 5000 = 5000, actual = 5005, difference = 5 (within 10)
        is_valid, _ = validator.validate_weight_equation(
            Decimal("10000"), Decimal("5000"), Decimal("5005")
        )
        assert is_valid

    def test_weight_equation_outside_tolerance(self, validator):
        """Test weight equation outside tolerance."""
        # 10000 - 5000 = 5000, actual = 5020, difference = 20 (outside 10)
        is_valid, _ = validator.validate_weight_equation(
            Decimal("10000"), Decimal("5000"), Decimal("5020")
        )
        assert not is_valid

    def test_validate_positive_weights(self, validator):
        """Test positive weight validation."""
        errors = validator.validate_positive_weights(
            Decimal("100"), Decimal("50"), Decimal("50")
        )
        assert len(errors) == 0

        errors = validator.validate_positive_weights(
            Decimal("-100"), Decimal("50"), Decimal("50")
        )
        assert len(errors) == 1
        assert "negative" in errors[0].lower()

    def test_validate_weight_order(self, validator):
        """Test weight order validation."""
        # Valid order
        errors = validator.validate_weight_order(
            Decimal("100"), Decimal("60"), Decimal("40")
        )
        assert len(errors) == 0

        # Invalid: tare > total
        errors = validator.validate_weight_order(
            Decimal("50"), Decimal("100"), Decimal("40")
        )
        assert len(errors) == 1

    def test_validate_all(self, validator):
        """Test comprehensive validation."""
        # Valid
        errors = validator.validate_all(
            Decimal("12480"), Decimal("7470"), Decimal("5010")
        )
        assert len(errors) == 0

        # Multiple errors
        errors = validator.validate_all(
            Decimal("-100"), Decimal("50"), Decimal("200")
        )
        assert len(errors) >= 2


class TestConfidenceValidator:
    """Tests for ConfidenceValidator."""

    @pytest.fixture
    def validator(self):
        return ConfidenceValidator()

    def test_check_confidence_high(self, validator):
        """Test high confidence check."""
        result = validator.check_confidence("field", 0.95)
        assert not result.low_confidence_flag
        assert result.confidence == 0.95

    def test_check_confidence_low(self, validator):
        """Test low confidence check."""
        result = validator.check_confidence("field", 0.6)
        assert result.low_confidence_flag
        assert result.confidence == 0.6

    def test_get_warning_message_critical(self, validator):
        """Test critical confidence warning."""
        message = validator.get_warning_message("field", 0.4)
        assert message is not None
        assert "CRITICAL" in message

    def test_get_warning_message_low(self, validator):
        """Test low confidence warning."""
        message = validator.get_warning_message("field", 0.6)
        assert message is not None
        assert "WARNING" in message

    def test_get_warning_message_ok(self, validator):
        """Test OK confidence (no warning)."""
        message = validator.get_warning_message("field", 0.8)
        assert message is None

    def test_filter_low_confidence_fields(self, validator):
        """Test filtering low confidence fields."""
        from weighing_parser.models.receipt import ExtractionConfidence

        scores = [
            ExtractionConfidence(field_name="a", confidence=0.9, low_confidence_flag=False),
            ExtractionConfidence(field_name="b", confidence=0.5, low_confidence_flag=True),
            ExtractionConfidence(field_name="c", confidence=0.6, low_confidence_flag=True),
        ]

        low = validator.filter_low_confidence_fields(scores)
        assert len(low) == 2

    def test_get_summary(self, validator):
        """Test confidence summary statistics."""
        from weighing_parser.models.receipt import ExtractionConfidence

        scores = [
            ExtractionConfidence(field_name="a", confidence=0.9, low_confidence_flag=False),
            ExtractionConfidence(field_name="b", confidence=0.5, low_confidence_flag=True),
            ExtractionConfidence(field_name="c", confidence=0.8, low_confidence_flag=False),
        ]

        summary = validator.get_summary(scores)
        assert summary["min"] == 0.5
        assert summary["max"] == 0.9
        assert summary["low_count"] == 1
        assert summary["total_count"] == 3
