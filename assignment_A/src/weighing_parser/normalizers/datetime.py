"""Date and time parsing and normalization."""

import re
from datetime import date, time
from typing import Optional, Tuple


class DateTimeNormalizer:
    """Handles parsing of various date and time formats from OCR text."""

    # Date patterns
    DATE_PATTERNS = [
        # YYYY-MM-DD (standard)
        (r"(\d{4})-(\d{2})-(\d{2})", lambda m: (int(m[1]), int(m[2]), int(m[3]))),
        # YYYY.MM.DD
        (r"(\d{4})\.(\d{2})\.(\d{2})", lambda m: (int(m[1]), int(m[2]), int(m[3]))),
        # YYYY/MM/DD
        (r"(\d{4})/(\d{2})/(\d{2})", lambda m: (int(m[1]), int(m[2]), int(m[3]))),
    ]

    # Time patterns
    TIME_PATTERNS = [
        # HH:MM:SS (standard)
        (r"(\d{1,2}):(\d{2}):(\d{2})", lambda m: (int(m[1]), int(m[2]), int(m[3]))),
        # HH:MM (without seconds)
        (r"(\d{1,2}):(\d{2})(?!:)", lambda m: (int(m[1]), int(m[2]), 0)),
        # HH시 MM분 (Korean format)
        (r"(\d{1,2})시\s*(\d{1,2})분", lambda m: (int(m[1]), int(m[2]), 0)),
        # (HH:MM) in parentheses
        (r"\((\d{1,2}):(\d{2})\)", lambda m: (int(m[1]), int(m[2]), 0)),
        # HH : MM with spaces
        (r"(\d{1,2})\s*:\s*(\d{2})(?!:)", lambda m: (int(m[1]), int(m[2]), 0)),
    ]

    @classmethod
    def parse_date(cls, text: str) -> Optional[date]:
        """
        Parse date from text in various formats.

        Examples:
        - '2026-02-02' -> date(2026, 2, 2)
        - '2026.02.02' -> date(2026, 2, 2)
        """
        for pattern, extractor in cls.DATE_PATTERNS:
            match = re.search(pattern, text)
            if match:
                try:
                    year, month, day = extractor(match)
                    return date(year, month, day)
                except ValueError:
                    continue
        return None

    @classmethod
    def parse_time(cls, text: str) -> Optional[time]:
        """
        Parse time from text in various formats.

        Examples:
        - '05:26:18' -> time(5, 26, 18)
        - '11시 33분' -> time(11, 33, 0)
        - '(09:09)' -> time(9, 9, 0)
        - '02 : 13' -> time(2, 13, 0)
        """
        for pattern, extractor in cls.TIME_PATTERNS:
            match = re.search(pattern, text)
            if match:
                try:
                    hour, minute, second = extractor(match)
                    return time(hour, minute, second)
                except ValueError:
                    continue
        return None

    @classmethod
    def parse_date_with_sequence(cls, text: str) -> Tuple[Optional[date], Optional[str]]:
        """
        Parse date that may have a sequence number.

        Examples:
        - '2026-02-02 0016' -> (date(2026, 2, 2), '0016')
        - '2026-02-02-00004' -> (date(2026, 2, 2), '00004')
        """
        # Pattern for date with hyphen-separated sequence
        match = re.search(r"(\d{4}-\d{2}-\d{2})-(\d+)", text)
        if match:
            parsed_date = cls.parse_date(match.group(1))
            return parsed_date, match.group(2)

        # Pattern for date with space-separated sequence
        match = re.search(r"(\d{4}-\d{2}-\d{2})\s+(\d{4,})", text)
        if match:
            parsed_date = cls.parse_date(match.group(1))
            return parsed_date, match.group(2)

        # Try just parsing the date without sequence
        parsed_date = cls.parse_date(text)
        return parsed_date, None

    @classmethod
    def extract_time_string(cls, text: str) -> Optional[str]:
        """
        Extract time as string for storage.

        Returns the original time format found in text.
        """
        # Try each pattern and return the matched string
        patterns = [
            r"\d{1,2}:\d{2}:\d{2}",  # HH:MM:SS
            r"\d{1,2}:\d{2}",  # HH:MM
            r"\d{1,2}시\s*\d{1,2}분",  # Korean format
            r"\(\d{1,2}:\d{2}\)",  # (HH:MM)
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group()
        return None

    @classmethod
    def parse_timestamp(cls, text: str) -> Optional[str]:
        """
        Parse full timestamp string.

        Example: '2026-02-02 05:37:55' -> '2026-02-02 05:37:55'
        """
        # Pattern for full timestamp
        match = re.search(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}", text)
        if match:
            return match.group()
        return None
