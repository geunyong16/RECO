"""Document type extractor."""

import re
from typing import Tuple, Optional

from .base import BaseExtractor
from ..models.ocr_input import OCRDocument
from ..normalizers.text import TextNormalizer


class DocumentTypeExtractor(BaseExtractor):
    """Extracts document type from OCR text."""

    # Document type patterns with their normalized names
    DOCUMENT_PATTERNS = {
        "계량증명서": [
            r"계\s*량\s*증\s*명\s*서",
            r"계량증명서",
        ],
        "계량확인서": [
            r"계\s*량\s*확\s*인\s*서",
            r"계량확인서",
        ],
        "계량증명표": [
            r"계\s*량\s*증\s*명\s*표",
            r"계량증명표",
        ],
        "계표": [
            r"계\s*[그근]\s*표",  # Handle OCR error: 그 for 근
            r"계표",
            r"계근표",
        ],
    }

    def extract(self, document: OCRDocument) -> Tuple[Optional[str], float]:
        """
        Extract document type from OCR document.

        Returns:
            Tuple of (document_type, confidence).
        """
        text = document.get_full_text()
        lines = document.get_lines()

        # Search in first few lines for document type header
        search_text = "\n".join([line.text for line in lines[:5]]) if lines else text

        for doc_type, patterns in self.DOCUMENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, search_text, re.IGNORECASE):
                    # Find confidence from the matching line
                    confidence = self._get_confidence_for_type(lines, patterns)
                    return doc_type, confidence

        return None, 0.0

    def _get_confidence_for_type(
        self, lines: list, patterns: list[str]
    ) -> float:
        """Get confidence score for the matched document type."""
        for line in lines[:5]:
            for pattern in patterns:
                if re.search(pattern, line.text, re.IGNORECASE):
                    return line.confidence
        return 0.8  # Default confidence if pattern found but line not matched
