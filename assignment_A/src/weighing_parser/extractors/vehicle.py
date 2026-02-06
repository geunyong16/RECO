"""Vehicle number extractor."""

import re
from typing import Tuple, Optional

from .base import BaseExtractor
from ..models.ocr_input import OCRDocument
from ..normalizers.text import TextNormalizer


class VehicleExtractor(BaseExtractor):
    """Extracts vehicle number from OCR text."""

    # Label patterns for vehicle number
    VEHICLE_LABELS = [
        "차량번호",
        "차량 번호",
        "차번호",
        "차 번 호",
        "차량 No",
        "차량No",
    ]

    # Vehicle number patterns
    VEHICLE_PATTERNS = [
        r"(\d{2,3}[가-힣]\d{4})",  # Korean plate: 80구8713
        r"(\d{4})",  # Simple 4-digit: 8713, 5405
    ]

    def extract(self, document: OCRDocument) -> Tuple[Optional[str], float]:
        """
        Extract vehicle number from OCR document.

        Returns:
            Tuple of (vehicle_number, confidence).
        """
        lines = document.get_lines()

        # Find line with vehicle label
        vehicle_line = self.find_line_containing(lines, self.VEHICLE_LABELS)

        if vehicle_line:
            # Extract vehicle number from this line
            vehicle_num = self._extract_from_line(vehicle_line.text)
            if vehicle_num:
                return vehicle_num, vehicle_line.confidence

            # Check next line if value not in same line
            next_line = self.get_next_line(lines, vehicle_line)
            if next_line:
                vehicle_num = self._extract_from_line(next_line.text)
                if vehicle_num:
                    return vehicle_num, next_line.confidence

        return None, 0.0

    def _extract_from_line(self, text: str) -> Optional[str]:
        """Extract vehicle number from a line of text."""
        # First try to get value after colon
        after_colon = TextNormalizer.extract_after_colon(text)
        if after_colon:
            text = after_colon

        # Try Korean plate format first (more specific)
        for pattern in self.VEHICLE_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return match.group(1)

        return None
