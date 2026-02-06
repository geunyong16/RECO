"""Weight fields extractor - handles total, tare, and net weight."""

from decimal import Decimal
from enum import Enum
from typing import Tuple, Optional, Dict

from .base import BaseExtractor
from ..models.ocr_input import OCRDocument, Line
from ..models.receipt import WeightMeasurement
from ..normalizers.numbers import NumberNormalizer
from ..normalizers.datetime import DateTimeNormalizer


class WeightType(Enum):
    """Types of weight measurements."""

    TOTAL = "total"
    TARE = "tare"
    NET = "net"


class WeightsExtractor(BaseExtractor):
    """
    Extracts weight measurements from OCR text using O(N) single-pass algorithm.

    Optimized from O(3N) to O(N) by scanning lines once and matching all weight
    types in a single pass.
    """

    # Label patterns mapped to weight types (ordered by specificity)
    # More specific labels should be checked first
    WEIGHT_LABEL_PRIORITY = [
        # Total weight labels (most specific)
        ("총중량", WeightType.TOTAL),
        ("총 중 량", WeightType.TOTAL),
        ("품종명랑", WeightType.TOTAL),  # OCR noise variant
        ("품종명", WeightType.TOTAL),
        # Tare weight labels (specific)
        ("공차중량", WeightType.TARE),
        ("공차 중량", WeightType.TARE),
        # Net weight labels
        ("실중량", WeightType.NET),
        ("실 중 량", WeightType.NET),
        # Tare weight labels (generic, lower priority)
        ("차중량", WeightType.TARE),
        ("차 중 량", WeightType.TARE),
        ("중 량", WeightType.TARE),
    ]

    def extract(
        self, document: OCRDocument
    ) -> Tuple[
        Optional[WeightMeasurement],
        Optional[WeightMeasurement],
        Optional[WeightMeasurement],
        float,
    ]:
        """
        Extract all weight measurements from OCR document in O(N) single pass.

        Args:
            document: OCR document to extract from.

        Returns:
            Tuple of (total_weight, tare_weight, net_weight, avg_confidence).
        """
        lines = document.get_lines()
        matches: Dict[WeightType, Tuple[WeightMeasurement, float]] = {}
        used_line_ids: set = set()

        # Single pass through all lines - O(N)
        for i, line in enumerate(lines):
            if line.id in used_line_ids:
                continue

            # Check each label in priority order
            for label, weight_type in self.WEIGHT_LABEL_PRIORITY:
                # Skip if we already found this weight type
                if weight_type in matches:
                    continue

                if label in line.text:
                    # Try to extract weight from this line
                    weight_kg = NumberNormalizer.extract_weight_from_line(line.text)
                    timestamp = DateTimeNormalizer.extract_time_string(line.text)

                    if weight_kg is None:
                        # Weight might be on next line
                        if i + 1 < len(lines):
                            next_line = lines[i + 1]
                            if next_line.id not in used_line_ids:
                                weight_kg = NumberNormalizer.extract_weight_from_line(
                                    next_line.text
                                )
                                if weight_kg is not None:
                                    timestamp = DateTimeNormalizer.extract_time_string(
                                        next_line.text
                                    )

                    if weight_kg is not None:
                        measurement = WeightMeasurement(
                            value_kg=weight_kg,
                            timestamp=timestamp,
                            confidence=line.confidence,
                        )
                        matches[weight_type] = (measurement, line.confidence)
                        used_line_ids.add(line.id)
                        break  # Found a match for this line, move to next line

        # Extract results
        total_result = matches.get(WeightType.TOTAL)
        tare_result = matches.get(WeightType.TARE)
        net_result = matches.get(WeightType.NET)

        total = total_result[0] if total_result else None
        tare = tare_result[0] if tare_result else None
        net = net_result[0] if net_result else None

        # Calculate average confidence
        confidences = [m[1] for m in matches.values()]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return total, tare, net, avg_confidence

    # Legacy methods for backward compatibility
    def extract_total(
        self, document: OCRDocument
    ) -> Tuple[Optional[WeightMeasurement], float]:
        """Extract total weight only."""
        total, _, _, conf = self.extract(document)
        return total, conf if total else 0.0

    def extract_tare(
        self, document: OCRDocument
    ) -> Tuple[Optional[WeightMeasurement], float]:
        """Extract tare weight only."""
        _, tare, _, conf = self.extract(document)
        return tare, conf if tare else 0.0

    def extract_net(
        self, document: OCRDocument
    ) -> Tuple[Optional[WeightMeasurement], float]:
        """Extract net weight only."""
        _, _, net, conf = self.extract(document)
        return net, conf if net else 0.0
