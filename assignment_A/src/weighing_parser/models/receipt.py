"""Pydantic models for parsed weighing receipt output."""

from decimal import Decimal
from pydantic import BaseModel, Field, field_serializer, model_validator, ConfigDict
from typing import Optional, Self, ClassVar
import datetime


class GPSCoordinates(BaseModel):
    """GPS location coordinates."""

    latitude: float
    longitude: float


class WeightMeasurement(BaseModel):
    """Weight measurement with optional timestamp and confidence."""

    value_kg: Decimal
    timestamp: Optional[str] = None
    confidence: float = 1.0

    @field_serializer("value_kg")
    def serialize_decimal(self, value: Decimal) -> str:
        """Serialize Decimal to string to preserve precision in JSON."""
        return str(value)


class ExtractionConfidence(BaseModel):
    """Confidence score for extracted field."""

    field_name: str
    confidence: float
    low_confidence_flag: bool = False


class WeighingReceipt(BaseModel):
    """Parsed weighing receipt data structure."""

    # Default validation tolerance constant (not a Pydantic field)
    # Can be overridden via weight_tolerance_kg field for DI
    DEFAULT_WEIGHT_TOLERANCE_KG: ClassVar[Decimal] = Decimal("10")

    # Document info
    document_type: Optional[str] = None

    # Date and sequence
    date: Optional[datetime.date] = None
    sequence_number: Optional[str] = None

    # Vehicle info
    vehicle_number: Optional[str] = None

    # Transaction info
    company_name: Optional[str] = None
    product_name: Optional[str] = None
    category: Optional[str] = None

    # Weight measurements
    total_weight: Optional[WeightMeasurement] = None
    tare_weight: Optional[WeightMeasurement] = None
    net_weight: Optional[WeightMeasurement] = None

    # Issuer info
    issuing_company: Optional[str] = None
    timestamp: Optional[str] = None

    # Location info
    gps_coordinates: Optional[GPSCoordinates] = None
    address: Optional[str] = None
    phone: Optional[str] = None

    # Metadata
    confidence_scores: list[ExtractionConfidence] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)
    raw_text: Optional[str] = None

    # Configurable tolerance (DI support)
    # If None, uses DEFAULT_WEIGHT_TOLERANCE_KG
    weight_tolerance_kg: Optional[Decimal] = Field(default=None, exclude=True)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def tolerance(self) -> Decimal:
        """Get effective tolerance (from DI or default)."""
        return self.weight_tolerance_kg or self.DEFAULT_WEIGHT_TOLERANCE_KG

    @model_validator(mode="after")
    def validate_weight_invariant(self) -> Self:
        """
        Enforce domain invariant: 실중량 = 총중량 - 공차중량.

        This validation runs after all fields are set.
        Adds validation error but does not raise exception to allow
        partial data handling.
        """
        # Skip if any required weight is missing
        if not (self.total_weight and self.tare_weight and self.net_weight):
            return self

        expected_net = self.total_weight.value_kg - self.tare_weight.value_kg
        actual_net = self.net_weight.value_kg
        difference = abs(expected_net - actual_net)

        if difference > self.tolerance:
            error_msg = (
                f"중량 불변식 위반: {self.total_weight.value_kg} - "
                f"{self.tare_weight.value_kg} = {expected_net}, "
                f"실중량: {actual_net} (차이: {difference} kg)"
            )
            if error_msg not in self.validation_errors:
                self.validation_errors.append(error_msg)

        # Validate positive weights
        for field_name, measurement in [
            ("총중량", self.total_weight),
            ("공차중량", self.tare_weight),
            ("실중량", self.net_weight),
        ]:
            if measurement and measurement.value_kg < 0:
                error_msg = f"{field_name} 음수: {measurement.value_kg} kg"
                if error_msg not in self.validation_errors:
                    self.validation_errors.append(error_msg)

        # Validate weight order (total >= tare)
        if self.total_weight.value_kg < self.tare_weight.value_kg:
            error_msg = (
                f"총중량({self.total_weight.value_kg} kg)이 "
                f"공차중량({self.tare_weight.value_kg} kg)보다 작음"
            )
            if error_msg not in self.validation_errors:
                self.validation_errors.append(error_msg)

        return self

    def to_flat_dict(self) -> dict:
        """Convert to flat dictionary for CSV export."""
        return {
            "document_type": self.document_type,
            "date": self.date.isoformat() if self.date else None,
            "sequence_number": self.sequence_number,
            "vehicle_number": self.vehicle_number,
            "company_name": self.company_name,
            "product_name": self.product_name,
            "category": self.category,
            "total_weight_kg": self.total_weight.value_kg if self.total_weight else None,
            "total_weight_time": self.total_weight.timestamp if self.total_weight else None,
            "tare_weight_kg": self.tare_weight.value_kg if self.tare_weight else None,
            "tare_weight_time": self.tare_weight.timestamp if self.tare_weight else None,
            "net_weight_kg": self.net_weight.value_kg if self.net_weight else None,
            "issuing_company": self.issuing_company,
            "timestamp": self.timestamp,
            "latitude": self.gps_coordinates.latitude if self.gps_coordinates else None,
            "longitude": self.gps_coordinates.longitude if self.gps_coordinates else None,
            "address": self.address,
            "phone": self.phone,
            "validation_errors": "; ".join(self.validation_errors) if self.validation_errors else None,
        }
