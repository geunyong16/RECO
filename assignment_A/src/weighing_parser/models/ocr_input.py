"""Pydantic models for Google Cloud Vision OCR JSON input."""

from pydantic import BaseModel
from typing import Optional, Any


class Vertex(BaseModel):
    """Bounding box vertex coordinate."""

    x: int
    y: int


class BoundingBox(BaseModel):
    """Bounding box for text regions."""

    vertices: list[Vertex]


class Word(BaseModel):
    """Individual word from OCR."""

    id: int
    text: str
    confidence: float
    boundingBox: BoundingBox


class Line(BaseModel):
    """Line of text from OCR."""

    id: int
    text: str
    confidence: float
    words: list[Word]
    boundingBox: Any  # Can be list or dict depending on OCR version


class Page(BaseModel):
    """Page of OCR results."""

    id: int
    text: str
    confidence: float
    width: int
    height: int
    words: list[Word]
    lines: list[Line]


class OCRDocument(BaseModel):
    """Complete OCR document from Google Cloud Vision API."""

    apiVersion: str
    confidence: float
    mimeType: Optional[str] = None
    text: str
    pages: list[Page]
    # Optional fields that may exist in API response
    modelVersion: Optional[str] = None
    numBilledPages: Optional[int] = None
    stored: Optional[bool] = None
    metadata: Optional[Any] = None

    def get_full_text(self) -> str:
        """Get the full text content of the document."""
        return self.text

    def get_lines(self) -> list[Line]:
        """Get all lines from all pages."""
        lines = []
        for page in self.pages:
            lines.extend(page.lines)
        return lines

    def get_line_texts(self) -> list[str]:
        """Get text content of all lines."""
        return [line.text for line in self.get_lines()]
