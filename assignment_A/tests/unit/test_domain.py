"""Unit tests for domain validation (model_validator in WeighingReceipt)."""

import pytest
from decimal import Decimal

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from weighing_parser.models.receipt import WeighingReceipt, WeightMeasurement


class TestWeighingReceiptDomainValidation:
    """Tests for domain validation in WeighingReceipt model_validator."""

    def test_valid_weight_invariant(self):
        """Test that valid weight invariant passes without errors."""
        receipt = WeighingReceipt(
            total_weight=WeightMeasurement(value_kg=Decimal("12480")),
            tare_weight=WeightMeasurement(value_kg=Decimal("7470")),
            net_weight=WeightMeasurement(value_kg=Decimal("5010")),
        )
        assert len(receipt.validation_errors) == 0

    def test_weight_invariant_violation(self):
        """Test that invalid weight invariant adds validation error."""
        receipt = WeighingReceipt(
            total_weight=WeightMeasurement(value_kg=Decimal("10000")),
            tare_weight=WeightMeasurement(value_kg=Decimal("5000")),
            net_weight=WeightMeasurement(value_kg=Decimal("4000")),  # Should be 5000
        )
        # Should have validation error for weight invariant violation
        assert any("불변식" in e for e in receipt.validation_errors)

    def test_weight_invariant_within_tolerance(self):
        """Test that weight invariant within tolerance passes."""
        # 10000 - 5000 = 5000, actual net = 5005, difference = 5 (within 10)
        receipt = WeighingReceipt(
            total_weight=WeightMeasurement(value_kg=Decimal("10000")),
            tare_weight=WeightMeasurement(value_kg=Decimal("5000")),
            net_weight=WeightMeasurement(value_kg=Decimal("5005")),
        )
        # Should pass - within tolerance
        invariant_errors = [e for e in receipt.validation_errors if "불변식" in e]
        assert len(invariant_errors) == 0

    def test_negative_weight_detection(self):
        """Test that negative weights are detected."""
        receipt = WeighingReceipt(
            total_weight=WeightMeasurement(value_kg=Decimal("-100")),
            tare_weight=WeightMeasurement(value_kg=Decimal("50")),
            net_weight=WeightMeasurement(value_kg=Decimal("50")),
        )
        assert any("음수" in e for e in receipt.validation_errors)

    def test_weight_order_violation(self):
        """Test that total < tare is detected."""
        receipt = WeighingReceipt(
            total_weight=WeightMeasurement(value_kg=Decimal("5000")),
            tare_weight=WeightMeasurement(value_kg=Decimal("10000")),  # tare > total
            net_weight=WeightMeasurement(value_kg=Decimal("1000")),
        )
        assert any("보다 작음" in e for e in receipt.validation_errors)

    def test_partial_weights_no_error(self):
        """Test that missing weights don't trigger validation."""
        # Only total weight - should not error
        receipt = WeighingReceipt(
            total_weight=WeightMeasurement(value_kg=Decimal("10000"))
        )
        invariant_errors = [e for e in receipt.validation_errors if "불변식" in e]
        assert len(invariant_errors) == 0

    def test_sample_01_weights(self):
        """Test with sample 01 data: total=12480, tare=7470, net=5010."""
        receipt = WeighingReceipt(
            document_type="계량증명서",
            total_weight=WeightMeasurement(value_kg=Decimal("12480")),
            tare_weight=WeightMeasurement(value_kg=Decimal("7470")),
            net_weight=WeightMeasurement(value_kg=Decimal("5010")),
        )
        assert len(receipt.validation_errors) == 0
        assert receipt.document_type == "계량증명서"

    def test_sample_02_weights(self):
        """Test with sample 02 data: total=13460, tare=7560, net=5900."""
        receipt = WeighingReceipt(
            total_weight=WeightMeasurement(value_kg=Decimal("13460")),
            tare_weight=WeightMeasurement(value_kg=Decimal("7560")),
            net_weight=WeightMeasurement(value_kg=Decimal("5900")),
        )
        assert len(receipt.validation_errors) == 0

    def test_sample_03_weights(self):
        """Test with sample 03 data: total=14080, tare=13950, net=130."""
        receipt = WeighingReceipt(
            total_weight=WeightMeasurement(value_kg=Decimal("14080")),
            tare_weight=WeightMeasurement(value_kg=Decimal("13950")),
            net_weight=WeightMeasurement(value_kg=Decimal("130")),
        )
        assert len(receipt.validation_errors) == 0

    def test_sample_04_weights(self):
        """Test with sample 04 data: total=14230, tare=12910, net=1320."""
        receipt = WeighingReceipt(
            total_weight=WeightMeasurement(value_kg=Decimal("14230")),
            tare_weight=WeightMeasurement(value_kg=Decimal("12910")),
            net_weight=WeightMeasurement(value_kg=Decimal("1320")),
        )
        assert len(receipt.validation_errors) == 0

    def test_multiple_validation_errors(self):
        """Test that multiple validation errors are collected."""
        receipt = WeighingReceipt(
            total_weight=WeightMeasurement(value_kg=Decimal("-100")),  # Negative
            tare_weight=WeightMeasurement(value_kg=Decimal("200")),  # > total
            net_weight=WeightMeasurement(value_kg=Decimal("-50")),  # Negative
        )
        # Should have multiple errors
        assert len(receipt.validation_errors) >= 2

    def test_validation_errors_not_duplicated(self):
        """Test that validation errors are not duplicated."""
        receipt = WeighingReceipt(
            total_weight=WeightMeasurement(value_kg=Decimal("10000")),
            tare_weight=WeightMeasurement(value_kg=Decimal("5000")),
            net_weight=WeightMeasurement(value_kg=Decimal("4000")),  # Invalid
        )
        # Count unique errors
        unique_errors = set(receipt.validation_errors)
        assert len(receipt.validation_errors) == len(unique_errors)


class TestWeighingReceiptConfigurableTolerance:
    """Tests for configurable weight tolerance (DI support)."""

    def test_default_tolerance(self):
        """Test that default tolerance is used when not specified."""
        receipt = WeighingReceipt(
            total_weight=WeightMeasurement(value_kg=Decimal("10000")),
            tare_weight=WeightMeasurement(value_kg=Decimal("5000")),
            net_weight=WeightMeasurement(value_kg=Decimal("5005")),  # Within default 10kg
        )
        assert receipt.tolerance == Decimal("10")
        invariant_errors = [e for e in receipt.validation_errors if "불변식" in e]
        assert len(invariant_errors) == 0

    def test_custom_tolerance_via_di(self):
        """Test custom tolerance via dependency injection."""
        # With strict tolerance (1kg), 5kg difference should fail
        receipt = WeighingReceipt(
            total_weight=WeightMeasurement(value_kg=Decimal("10000")),
            tare_weight=WeightMeasurement(value_kg=Decimal("5000")),
            net_weight=WeightMeasurement(value_kg=Decimal("5005")),  # 5kg difference
            weight_tolerance_kg=Decimal("1"),  # DI: strict tolerance
        )
        assert receipt.tolerance == Decimal("1")
        invariant_errors = [e for e in receipt.validation_errors if "불변식" in e]
        assert len(invariant_errors) == 1  # Should have error

    def test_custom_tolerance_passes(self):
        """Test custom tolerance that allows the difference."""
        receipt = WeighingReceipt(
            total_weight=WeightMeasurement(value_kg=Decimal("10000")),
            tare_weight=WeightMeasurement(value_kg=Decimal("5000")),
            net_weight=WeightMeasurement(value_kg=Decimal("4900")),  # 100kg difference
            weight_tolerance_kg=Decimal("100"),  # DI: lenient tolerance
        )
        assert receipt.tolerance == Decimal("100")
        invariant_errors = [e for e in receipt.validation_errors if "불변식" in e]
        assert len(invariant_errors) == 0  # Should pass with lenient tolerance

    def test_tolerance_not_serialized(self):
        """Test that weight_tolerance_kg is excluded from serialization."""
        receipt = WeighingReceipt(
            total_weight=WeightMeasurement(value_kg=Decimal("10000")),
            weight_tolerance_kg=Decimal("20"),
        )
        data = receipt.model_dump()
        assert "weight_tolerance_kg" not in data


class TestWeightMeasurementDecimal:
    """Tests for WeightMeasurement Decimal type."""

    def test_value_kg_is_decimal(self):
        """Test that value_kg is stored as Decimal."""
        measurement = WeightMeasurement(value_kg=Decimal("12480"))
        assert isinstance(measurement.value_kg, Decimal)

    def test_value_kg_accepts_string_decimal(self):
        """Test that value_kg accepts Decimal from string."""
        measurement = WeightMeasurement(value_kg=Decimal("12480.5"))
        assert measurement.value_kg == Decimal("12480.5")

    def test_serialization_preserves_precision(self):
        """Test that Decimal serialization preserves precision."""
        measurement = WeightMeasurement(value_kg=Decimal("12480"))
        data = measurement.model_dump()
        assert data["value_kg"] == "12480"  # Serialized as string

    def test_timestamp_optional(self):
        """Test that timestamp is optional."""
        m1 = WeightMeasurement(value_kg=Decimal("1000"))
        m2 = WeightMeasurement(value_kg=Decimal("1000"), timestamp="05:26:18")

        assert m1.timestamp is None
        assert m2.timestamp == "05:26:18"

    def test_confidence_default(self):
        """Test that confidence has default value."""
        measurement = WeightMeasurement(value_kg=Decimal("1000"))
        assert measurement.confidence == 1.0

    def test_confidence_custom(self):
        """Test that confidence can be set."""
        measurement = WeightMeasurement(value_kg=Decimal("1000"), confidence=0.85)
        assert measurement.confidence == 0.85
