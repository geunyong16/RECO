"""Base class for field extractors."""

from abc import ABC, abstractmethod
from typing import Any, Tuple, Optional

from ..models.ocr_input import OCRDocument, Line


class BaseExtractor(ABC):
    """Abstract base class for field extractors."""

    def __init__(self, min_confidence: float = 0.5):
        """
        Initialize extractor.

        Args:
            min_confidence: Minimum confidence threshold for extraction.
        """
        self.min_confidence = min_confidence

    @abstractmethod
    def extract(self, document: OCRDocument) -> Tuple[Optional[Any], float]:
        """
        Extract field value from OCR document.

        Args:
            document: Parsed OCR document.

        Returns:
            Tuple of (extracted_value, confidence_score).
            Value is None if extraction fails.
        """
        pass

    def find_line_containing(
        self, lines: list[Line], patterns: list[str], case_insensitive: bool = False
    ) -> Optional[Line]:
        """
        Find first line containing any of the patterns.

        Args:
            lines: List of OCR lines.
            patterns: List of text patterns to search for.
            case_insensitive: Whether to ignore case.

        Returns:
            First matching line or None.
        """
        for line in lines:
            text = line.text.lower() if case_insensitive else line.text
            for pattern in patterns:
                check = pattern.lower() if case_insensitive else pattern
                if check in text:
                    return line
        return None

    def find_all_lines_containing(
        self, lines: list[Line], patterns: list[str], case_insensitive: bool = False
    ) -> list[Line]:
        """
        Find all lines containing any of the patterns.

        Args:
            lines: List of OCR lines.
            patterns: List of text patterns to search for.
            case_insensitive: Whether to ignore case.

        Returns:
            List of matching lines.
        """
        matches = []
        for line in lines:
            text = line.text.lower() if case_insensitive else line.text
            for pattern in patterns:
                check = pattern.lower() if case_insensitive else pattern
                if check in text:
                    matches.append(line)
                    break
        return matches

    def get_line_index(self, lines: list[Line], target_line: Line) -> int:
        """Get index of line in lines list."""
        for i, line in enumerate(lines):
            if line.id == target_line.id:
                return i
        return -1

    def get_next_line(self, lines: list[Line], current_line: Line) -> Optional[Line]:
        """Get the line after current_line."""
        idx = self.get_line_index(lines, current_line)
        if idx >= 0 and idx < len(lines) - 1:
            return lines[idx + 1]
        return None
