"""Text normalization for OCR noise handling."""

import re


class TextNormalizer:
    """Handles Korean text normalization and OCR error correction."""

    # Common OCR misreadings to correct
    OCR_CORRECTIONS = {
        "계 그 표": "계표",
        "계그표": "계표",
        "품종명랑": "품종명",
    }

    @staticmethod
    def remove_spaces(text: str) -> str:
        """
        Remove spaces from Korean text.

        Example: '계 량 증 명 서' -> '계량증명서'
        """
        return text.replace(" ", "")

    @staticmethod
    def normalize_korean_spaces(text: str) -> str:
        """
        Remove spaces between Korean characters while preserving
        spaces between other characters.

        Example: '계 량 증 명 서' -> '계량증명서'
        """
        # Remove spaces between Korean characters
        pattern = r"([가-힣])\s+([가-힣])"
        while re.search(pattern, text):
            text = re.sub(pattern, r"\1\2", text)
        return text

    @classmethod
    def fix_ocr_errors(cls, text: str) -> str:
        """
        Fix common OCR misreadings.

        Example: '계 그 표' -> '계표' (그 is misread from 근)
        """
        for wrong, correct in cls.OCR_CORRECTIONS.items():
            text = text.replace(wrong, correct)
        return text

    @classmethod
    def normalize(cls, text: str) -> str:
        """
        Apply all text normalizations.

        1. Fix OCR errors
        2. Normalize Korean spaces
        """
        text = cls.fix_ocr_errors(text)
        text = cls.normalize_korean_spaces(text)
        return text

    @staticmethod
    def clean_label(text: str) -> str:
        """
        Clean field label by removing colons, spaces, and special chars.

        Example: '차량 번호:' -> '차량번호'
        """
        text = text.replace(":", "").replace("：", "")
        text = text.replace(" ", "")
        return text.strip()

    @staticmethod
    def extract_after_colon(text: str) -> str | None:
        """
        Extract value after colon in 'label: value' format.

        Example: '차량번호: 8713' -> '8713'
        """
        if ":" in text:
            parts = text.split(":", 1)
            if len(parts) == 2:
                return parts[1].strip()
        if "：" in text:
            parts = text.split("：", 1)
            if len(parts) == 2:
                return parts[1].strip()
        return None
