"""Company name extractors for trading partner and issuer."""

import re
from typing import Tuple, Optional

from .base import BaseExtractor
from ..models.ocr_input import OCRDocument
from ..normalizers.text import TextNormalizer


class CompanyExtractor(BaseExtractor):
    """Extracts company/trading partner name from OCR text."""

    # Label patterns for company name
    COMPANY_LABELS = [
        "거래처",
        "거 래 처",
        "상호",
        "상 호",
        "회사명",
        "회 사 명",
    ]

    def extract(self, document: OCRDocument) -> Tuple[Optional[str], float]:
        """
        Extract company name from OCR document.

        Returns:
            Tuple of (company_name, confidence).
        """
        lines = document.get_lines()

        # Find line with company label
        company_line = self.find_line_containing(lines, self.COMPANY_LABELS)

        if company_line:
            # Extract company name from this line
            company = self._extract_from_line(company_line.text)
            if company:
                return company, company_line.confidence

            # Check next line if value not in same line
            next_line = self.get_next_line(lines, company_line)
            if next_line:
                # Use the whole next line as company name if it's not a label
                text = next_line.text.strip()
                if not self._is_label_line(text):
                    return text, next_line.confidence

        return None, 0.0

    def _extract_from_line(self, text: str) -> Optional[str]:
        """Extract company name from a line of text."""
        after_colon = TextNormalizer.extract_after_colon(text)
        if after_colon:
            return after_colon.strip()

        # Try to extract after label
        for label in self.COMPANY_LABELS:
            normalized_label = label.replace(" ", "")
            normalized_text = text.replace(" ", "")
            if normalized_label in normalized_text:
                idx = normalized_text.find(normalized_label)
                remainder = text[idx + len(label) :].strip()
                if remainder:
                    return remainder

        return None

    def _is_label_line(self, text: str) -> bool:
        """Check if line is just a label without value."""
        labels = [
            "품명",
            "품 명",
            "제품명",
            "총중량",
            "공차",
            "실중량",
            "차량",
        ]
        normalized = text.replace(" ", "").replace(":", "")
        for label in labels:
            if normalized.startswith(label.replace(" ", "")):
                return True
        return False


class IssuerExtractor(BaseExtractor):
    """Extracts issuing company name from OCR text."""

    # Known issuer patterns (company names that appear at bottom)
    ISSUER_PATTERNS = [
        r"([\w가-힣]+\s*\(주\))",  # Something (주)
        r"\(주\)\s*([\w가-힣]+)",  # (주) Something
        r"([\w가-힣]+주식회사)",  # Something주식회사
        r"([\w가-힣]+C&S)",  # Something C&S
        r"([\w가-힣]+바이오)",  # Something바이오
        r"([\w가-힣]+리사이클링)",  # Something리사이클링
        r"([\w가-힣]+펄프)",  # Something펄프
    ]

    def extract(self, document: OCRDocument) -> Tuple[Optional[str], float]:
        """
        Extract issuing company from OCR document.

        Issuers typically appear at the bottom of the document.

        Returns:
            Tuple of (issuer_name, confidence).
        """
        lines = document.get_lines()
        text = document.get_full_text()

        # Search from bottom lines up
        for line in reversed(lines[-10:]):
            for pattern in self.ISSUER_PATTERNS:
                match = re.search(pattern, line.text)
                if match:
                    return match.group(0), line.confidence

        # Fallback: search full text
        for pattern in self.ISSUER_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return match.group(0), document.confidence

        return None, 0.0
