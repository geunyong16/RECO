"""Date and sequence number extractor."""

import re
from datetime import date
from typing import Tuple, Optional

from .base import BaseExtractor
from ..models.ocr_input import OCRDocument
from ..normalizers.datetime import DateTimeNormalizer


class DateExtractor(BaseExtractor):
    """Extracts date and sequence number from OCR text."""

    # Label patterns for date fields
    DATE_LABELS = [
        "계량일자",
        "계량 일자",
        "날 짜",
        "날짜",
        "일 시",
        "일시",
    ]

    def extract(self, document: OCRDocument) -> Tuple[Optional[date], float]:
        """
        Extract date from OCR document.

        Returns:
            Tuple of (date, confidence).
        """
        lines = document.get_lines()

        # Find line with date label
        date_line = self.find_line_containing(lines, self.DATE_LABELS)

        if date_line:
            # Try to extract date from this line
            parsed_date = DateTimeNormalizer.parse_date(date_line.text)
            if parsed_date:
                return parsed_date, date_line.confidence

            # Maybe date is on next line
            next_line = self.get_next_line(lines, date_line)
            if next_line:
                parsed_date = DateTimeNormalizer.parse_date(next_line.text)
                if parsed_date:
                    return parsed_date, next_line.confidence

        # Fallback: search entire text for date pattern
        text = document.get_full_text()
        parsed_date = DateTimeNormalizer.parse_date(text)
        if parsed_date:
            return parsed_date, document.confidence

        return None, 0.0

    def extract_with_sequence(
        self, document: OCRDocument
    ) -> Tuple[Optional[date], Optional[str], float]:
        """
        Extract date and sequence number from OCR document.

        Returns:
            Tuple of (date, sequence_number, confidence).
        """
        lines = document.get_lines()

        # Find line with date label
        date_line = self.find_line_containing(lines, self.DATE_LABELS)

        if date_line:
            parsed_date, sequence = DateTimeNormalizer.parse_date_with_sequence(
                date_line.text
            )
            if parsed_date:
                return parsed_date, sequence, date_line.confidence

        # Fallback to full text
        text = document.get_full_text()
        parsed_date, sequence = DateTimeNormalizer.parse_date_with_sequence(text)
        if parsed_date:
            return parsed_date, sequence, document.confidence

        return None, None, 0.0
