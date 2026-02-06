"""Enumeration types for document classification."""

from enum import Enum


class DocumentType(Enum):
    """Types of weighing documents."""

    WEIGHING_CERTIFICATE = "계량증명서"
    WEIGHING_CONFIRMATION = "계량확인서"
    WEIGHING_SLIP = "계량증명표"
    WEIGHING_FORM = "계표"

    @classmethod
    def from_text(cls, text: str) -> "DocumentType | None":
        """Match document type from normalized text."""
        text_normalized = text.replace(" ", "")
        for doc_type in cls:
            if doc_type.value in text_normalized:
                return doc_type
        return None


class Category(Enum):
    """Transaction category (incoming/outgoing)."""

    INCOMING = "입고"
    OUTGOING = "출고"

    @classmethod
    def from_text(cls, text: str) -> "Category | None":
        """Match category from text."""
        if "입고" in text:
            return cls.INCOMING
        if "출고" in text:
            return cls.OUTGOING
        return None
