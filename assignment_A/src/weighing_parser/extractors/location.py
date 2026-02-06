"""Location extractors for GPS coordinates and address."""

import re
from typing import Tuple, Optional

from .base import BaseExtractor
from ..models.ocr_input import OCRDocument
from ..models.receipt import GPSCoordinates
from ..normalizers.numbers import NumberNormalizer


class LocationExtractor(BaseExtractor):
    """Extracts GPS coordinates and address from OCR text."""

    # GPS coordinate pattern
    GPS_PATTERN = r"(\d{1,3}\.\d+)\s*,\s*(\d{1,3}\.\d+)"

    # Address indicators
    ADDRESS_PATTERNS = [
        r"((?:서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)(?:특별시|광역시|도|특별자치시|특별자치도)?[\w\s가-힣\d\-]+(?:길|로|동|읍|면|리)[\w\s가-힣\d\-]*)",
    ]

    def extract_gps(
        self, document: OCRDocument
    ) -> Tuple[Optional[GPSCoordinates], float]:
        """
        Extract GPS coordinates from OCR document.

        GPS coordinates typically appear at the bottom of some documents.

        Returns:
            Tuple of (GPSCoordinates, confidence).
        """
        lines = document.get_lines()

        # Search from bottom lines
        for line in reversed(lines[-5:]):
            match = re.search(self.GPS_PATTERN, line.text)
            if match:
                lat = NumberNormalizer.parse_decimal(match.group(1))
                lon = NumberNormalizer.parse_decimal(match.group(2))
                if lat and lon:
                    # Validate reasonable ranges for Korea
                    if 33 <= lat <= 43 and 124 <= lon <= 132:
                        return (
                            GPSCoordinates(latitude=lat, longitude=lon),
                            line.confidence,
                        )

        return None, 0.0

    def extract_address(self, document: OCRDocument) -> Tuple[Optional[str], float]:
        """
        Extract address from OCR document.

        Returns:
            Tuple of (address, confidence).
        """
        lines = document.get_lines()
        text = document.get_full_text()

        # Try pattern matching first
        for pattern in self.ADDRESS_PATTERNS:
            match = re.search(pattern, text)
            if match:
                address = match.group(1).strip()
                # Find confidence from matching line
                for line in lines:
                    if address[:10] in line.text:
                        return address, line.confidence
                return address, document.confidence

        # Look for lines containing address indicators
        address_indicators = ["시", "도", "군", "구", "동", "로", "길"]
        for line in lines:
            indicator_count = sum(1 for ind in address_indicators if ind in line.text)
            if indicator_count >= 3:
                # This might be an address line
                return line.text.strip(), line.confidence

        return None, 0.0

    def extract(
        self, document: OCRDocument
    ) -> Tuple[Optional[GPSCoordinates], Optional[str], float]:
        """
        Extract both GPS and address.

        Returns:
            Tuple of (gps, address, avg_confidence).
        """
        gps, gps_conf = self.extract_gps(document)
        address, addr_conf = self.extract_address(document)

        confidences = [c for c in [gps_conf, addr_conf] if c > 0]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        return gps, address, avg_conf
