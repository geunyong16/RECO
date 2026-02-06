"""Contact information extractor (phone, fax)."""

import re
from typing import Tuple, Optional

from .base import BaseExtractor
from ..models.ocr_input import OCRDocument


class ContactExtractor(BaseExtractor):
    """Extracts contact information from OCR text."""

    # Phone number patterns
    PHONE_PATTERNS = [
        r"(?:Tel|TEL|전화|연락처)[\s:)]*(\d{2,4}[-)\s]?\d{3,4}[-\s]?\d{4})",
        r"(\d{2,3}-\d{3,4}-\d{4})",  # Standard Korean phone format
        r"\((\d{3})\)\s*(\d{3,4})-(\d{4})",  # (031)359-9127 format
    ]

    # Fax patterns
    FAX_PATTERNS = [
        r"(?:Fax|FAX|팩스)[\s:)]*(\d{2,4}[-)\s]?\d{3,4}[-\s]?\d{4})",
    ]

    def extract(self, document: OCRDocument) -> Tuple[Optional[str], float]:
        """
        Extract phone number from OCR document.

        Returns:
            Tuple of (phone_number, confidence).
        """
        lines = document.get_lines()
        text = document.get_full_text()

        # Search for phone patterns
        for pattern in self.PHONE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                phone = self._normalize_phone(match)
                # Find confidence from matching line
                for line in lines:
                    if phone[:8] in line.text.replace(" ", "").replace("-", ""):
                        return phone, line.confidence
                return phone, document.confidence

        return None, 0.0

    def extract_fax(self, document: OCRDocument) -> Tuple[Optional[str], float]:
        """
        Extract fax number from OCR document.

        Returns:
            Tuple of (fax_number, confidence).
        """
        text = document.get_full_text()

        for pattern in self.FAX_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return self._normalize_phone(match), document.confidence

        return None, 0.0

    def _normalize_phone(self, match: re.Match) -> str:
        """Normalize phone number to standard format."""
        # Get all groups and join
        groups = [g for g in match.groups() if g]
        if len(groups) == 1:
            phone = groups[0]
        else:
            phone = "-".join(groups)

        # Remove extra characters and normalize
        phone = re.sub(r"[^\d-]", "", phone)

        # Ensure proper hyphen placement if missing
        if "-" not in phone and len(phone) >= 9:
            if len(phone) == 10:
                phone = f"{phone[:3]}-{phone[3:6]}-{phone[6:]}"
            elif len(phone) == 11:
                phone = f"{phone[:3]}-{phone[3:7]}-{phone[7:]}"

        return phone
