"""Number parsing and normalization."""

import re
from decimal import Decimal, InvalidOperation
from typing import Optional, Union


class NumberNormalizer:
    """Handles parsing of numbers from OCR text."""

    @staticmethod
    def parse_weight(text: str) -> Optional[Decimal]:
        """
        Parse weight string to Decimal kg value.

        Uses strict string parsing to avoid floating point errors.
        Handles various OCR formats:
        - '12,480' -> Decimal('12480') (comma-separated)
        - '5 900' -> Decimal('5900') (space-separated)
        - '13 460 kg' -> Decimal('13460') (with unit)
        - '7,470 kg' -> Decimal('7470')

        Returns None if parsing fails.
        """
        if not text:
            return None

        # Remove 'kg' unit if present
        text = re.sub(r"\s*kg\s*$", "", text, flags=re.IGNORECASE)

        # Remove commas
        text = text.replace(",", "")

        # Remove spaces between digit groups
        text = re.sub(r"(\d)\s+(\d)", r"\1\2", text)

        # Remove any remaining non-digit characters except minus and dot
        text = re.sub(r"[^\d.\-]", "", text)

        # Extract the number (supports decimal point)
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        if match:
            try:
                return Decimal(match.group())
            except InvalidOperation:
                return None
        return None

    @staticmethod
    def parse_decimal(text: str) -> Optional[float]:
        """
        Parse decimal number (e.g., GPS coordinates).

        Example: '37.105317' -> 37.105317
        """
        if not text:
            return None

        # Remove any non-numeric characters except dot and minus
        text = re.sub(r"[^\d.-]", "", text)

        try:
            return float(text)
        except ValueError:
            return None

    @staticmethod
    def format_weight(value: Union[Decimal, int]) -> str:
        """
        Format weight value with comma separators.

        Example: Decimal('12480') -> '12,480'
        """
        int_part = int(value)
        return f"{int_part:,}"

    @staticmethod
    def extract_weight_from_line(text: str) -> Optional[Decimal]:
        """
        Extract weight value from a line that may contain other info.

        Example: '05:26:18 12,480 kg' -> Decimal('12480')
        Example: '13 460 kg' -> Decimal('13460')
        """
        # Remove time patterns to avoid confusion with numbers
        text_clean = re.sub(r"\d{1,2}:\d{2}(:\d{2})?", "", text)

        # Pattern to match weight value with kg unit
        # Order matters: try space-separated first (most specific), then comma, then simple
        patterns = [
            r"(\d+\s+\d+)\s*kg",  # 13 460 kg (space-separated)
            r"([\d,]+)\s*kg",  # 12,480 kg (comma-separated)
            r"(\d+)\s*kg",  # 130 kg (simple number)
        ]

        for pattern in patterns:
            match = re.search(pattern, text_clean, re.IGNORECASE)
            if match:
                return NumberNormalizer.parse_weight(match.group(1))

        return None
