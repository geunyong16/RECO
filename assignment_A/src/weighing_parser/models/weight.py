"""Weight Value Object for domain-driven weight operations."""

from decimal import Decimal
from pydantic import BaseModel, field_serializer
from typing import Union


class Weight(BaseModel):
    """
    Immutable Value Object representing a weight measurement.

    Provides unit conversion and comparison operations.
    All operations return new instances (immutable pattern).
    """

    value_kg: Decimal

    model_config = {"frozen": True}  # Make immutable

    @classmethod
    def from_kg(cls, kg: Union[Decimal, int, float, str]) -> "Weight":
        """Create Weight from kilograms."""
        return cls(value_kg=Decimal(str(kg)))

    @classmethod
    def from_ton(cls, ton: Union[Decimal, int, float, str]) -> "Weight":
        """Create Weight from metric tons."""
        return cls(value_kg=Decimal(str(ton)) * Decimal("1000"))

    @classmethod
    def zero(cls) -> "Weight":
        """Create a zero weight."""
        return cls(value_kg=Decimal("0"))

    @property
    def kg(self) -> Decimal:
        """Get value in kilograms."""
        return self.value_kg

    @property
    def ton(self) -> Decimal:
        """Get value in metric tons."""
        return self.value_kg / Decimal("1000")

    def __sub__(self, other: "Weight") -> "Weight":
        """Subtract weights."""
        if not isinstance(other, Weight):
            return NotImplemented
        return Weight(value_kg=self.value_kg - other.value_kg)

    def __add__(self, other: "Weight") -> "Weight":
        """Add weights."""
        if not isinstance(other, Weight):
            return NotImplemented
        return Weight(value_kg=self.value_kg + other.value_kg)

    def __neg__(self) -> "Weight":
        """Negate weight."""
        return Weight(value_kg=-self.value_kg)

    def __abs__(self) -> "Weight":
        """Absolute value of weight."""
        return Weight(value_kg=abs(self.value_kg))

    def __lt__(self, other: "Weight") -> bool:
        if not isinstance(other, Weight):
            return NotImplemented
        return self.value_kg < other.value_kg

    def __le__(self, other: "Weight") -> bool:
        if not isinstance(other, Weight):
            return NotImplemented
        return self.value_kg <= other.value_kg

    def __gt__(self, other: "Weight") -> bool:
        if not isinstance(other, Weight):
            return NotImplemented
        return self.value_kg > other.value_kg

    def __ge__(self, other: "Weight") -> bool:
        if not isinstance(other, Weight):
            return NotImplemented
        return self.value_kg >= other.value_kg

    def is_positive(self) -> bool:
        """Check if weight is positive."""
        return self.value_kg > 0

    def is_negative(self) -> bool:
        """Check if weight is negative."""
        return self.value_kg < 0

    def is_zero(self) -> bool:
        """Check if weight is zero."""
        return self.value_kg == 0

    def approximately_equals(
        self, other: "Weight", tolerance_kg: Union[Decimal, int] = Decimal("10")
    ) -> bool:
        """
        Check if weights are approximately equal within tolerance.

        Args:
            other: Weight to compare with.
            tolerance_kg: Maximum allowed difference in kg.

        Returns:
            True if weights differ by no more than tolerance_kg.
        """
        if not isinstance(other, Weight):
            return False
        tolerance = Decimal(str(tolerance_kg))
        return abs(self.value_kg - other.value_kg) <= tolerance

    @field_serializer("value_kg")
    def serialize_decimal(self, value: Decimal) -> str:
        """Serialize Decimal to string to preserve precision."""
        return str(value)

    def __repr__(self) -> str:
        return f"Weight({self.value_kg} kg)"

    def __str__(self) -> str:
        return f"{self.value_kg} kg"
