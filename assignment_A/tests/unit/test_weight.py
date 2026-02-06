"""Unit tests for Weight Value Object."""

import pytest
from decimal import Decimal

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from weighing_parser.models.weight import Weight


class TestWeight:
    """Tests for Weight Value Object."""

    def test_from_kg(self):
        """Test creating Weight from kilograms."""
        w = Weight.from_kg(Decimal("1000"))
        assert w.kg == Decimal("1000")
        assert w.ton == Decimal("1")

    def test_from_kg_with_int(self):
        """Test creating Weight from integer kg."""
        w = Weight.from_kg(1000)
        assert w.kg == Decimal("1000")

    def test_from_ton(self):
        """Test creating Weight from tons."""
        w = Weight.from_ton(Decimal("1.5"))
        assert w.kg == Decimal("1500")
        assert w.ton == Decimal("1.5")

    def test_zero(self):
        """Test creating zero weight."""
        w = Weight.zero()
        assert w.kg == Decimal("0")
        assert w.is_zero()

    def test_subtraction(self):
        """Test weight subtraction."""
        total = Weight.from_kg(Decimal("12480"))
        tare = Weight.from_kg(Decimal("7470"))
        net = total - tare

        assert net.kg == Decimal("5010")

    def test_addition(self):
        """Test weight addition."""
        tare = Weight.from_kg(Decimal("7470"))
        net = Weight.from_kg(Decimal("5010"))
        total = tare + net

        assert total.kg == Decimal("12480")

    def test_negation(self):
        """Test weight negation."""
        w = Weight.from_kg(Decimal("1000"))
        neg_w = -w
        assert neg_w.kg == Decimal("-1000")

    def test_abs(self):
        """Test absolute value of weight."""
        neg_w = Weight.from_kg(Decimal("-1000"))
        abs_w = abs(neg_w)
        assert abs_w.kg == Decimal("1000")

    def test_comparison_lt(self):
        """Test less than comparison."""
        w1 = Weight.from_kg(Decimal("1000"))
        w2 = Weight.from_kg(Decimal("2000"))
        assert w1 < w2
        assert not w2 < w1

    def test_comparison_le(self):
        """Test less than or equal comparison."""
        w1 = Weight.from_kg(Decimal("1000"))
        w2 = Weight.from_kg(Decimal("1000"))
        w3 = Weight.from_kg(Decimal("2000"))
        assert w1 <= w2
        assert w1 <= w3

    def test_comparison_gt(self):
        """Test greater than comparison."""
        w1 = Weight.from_kg(Decimal("2000"))
        w2 = Weight.from_kg(Decimal("1000"))
        assert w1 > w2
        assert not w2 > w1

    def test_comparison_ge(self):
        """Test greater than or equal comparison."""
        w1 = Weight.from_kg(Decimal("2000"))
        w2 = Weight.from_kg(Decimal("2000"))
        w3 = Weight.from_kg(Decimal("1000"))
        assert w1 >= w2
        assert w1 >= w3

    def test_is_positive(self):
        """Test positive weight check."""
        pos = Weight.from_kg(Decimal("1000"))
        neg = Weight.from_kg(Decimal("-1000"))
        zero = Weight.zero()

        assert pos.is_positive()
        assert not neg.is_positive()
        assert not zero.is_positive()

    def test_is_negative(self):
        """Test negative weight check."""
        pos = Weight.from_kg(Decimal("1000"))
        neg = Weight.from_kg(Decimal("-1000"))
        zero = Weight.zero()

        assert not pos.is_negative()
        assert neg.is_negative()
        assert not zero.is_negative()

    def test_approximately_equals(self):
        """Test approximate equality within tolerance."""
        w1 = Weight.from_kg(Decimal("1000"))
        w2 = Weight.from_kg(Decimal("1005"))
        w3 = Weight.from_kg(Decimal("1015"))

        assert w1.approximately_equals(w2, tolerance_kg=Decimal("10"))
        assert not w1.approximately_equals(w3, tolerance_kg=Decimal("10"))

    def test_approximately_equals_default_tolerance(self):
        """Test approximate equality with default tolerance."""
        w1 = Weight.from_kg(Decimal("1000"))
        w2 = Weight.from_kg(Decimal("1010"))
        w3 = Weight.from_kg(Decimal("1011"))

        assert w1.approximately_equals(w2)  # Default tolerance is 10
        assert not w1.approximately_equals(w3)

    def test_immutability(self):
        """Test that Weight is immutable."""
        w = Weight.from_kg(Decimal("1000"))
        with pytest.raises(Exception):  # ValidationError for frozen model
            w.value_kg = Decimal("2000")

    def test_str_repr(self):
        """Test string representation."""
        w = Weight.from_kg(Decimal("1234"))
        assert "1234" in str(w)
        assert "kg" in str(w)

    def test_equality(self):
        """Test weight equality."""
        w1 = Weight.from_kg(Decimal("1000"))
        w2 = Weight.from_kg(Decimal("1000"))
        w3 = Weight.from_kg(Decimal("2000"))

        assert w1 == w2
        assert w1 != w3

    def test_sample_data_calculation(self):
        """Test weight calculation with sample data values."""
        # Sample 01: total=12480, tare=7470, net=5010
        total = Weight.from_kg(Decimal("12480"))
        tare = Weight.from_kg(Decimal("7470"))
        expected_net = Weight.from_kg(Decimal("5010"))

        calculated_net = total - tare
        assert calculated_net == expected_net
        assert calculated_net.approximately_equals(expected_net)
