"""Pytest configuration and fixtures."""

import pytest
from pathlib import Path
import json


@pytest.fixture
def sample_data_dir():
    """Path to sample OCR data directory."""
    # Adjust path based on actual location
    base = Path(__file__).parent.parent
    sample_dir = base / "[2026 ICT_리코] smaple_data_ocr"
    return sample_dir


@pytest.fixture
def sample_receipt_01(sample_data_dir):
    """Load sample receipt 01 JSON."""
    filepath = sample_data_dir / "receipt_01.json"
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


@pytest.fixture
def sample_receipt_02(sample_data_dir):
    """Load sample receipt 02 JSON."""
    filepath = sample_data_dir / "receipt_02.json"
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


@pytest.fixture
def sample_receipt_03(sample_data_dir):
    """Load sample receipt 03 JSON."""
    filepath = sample_data_dir / "receipt_03.json"
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


@pytest.fixture
def sample_receipt_04(sample_data_dir):
    """Load sample receipt 04 JSON."""
    filepath = sample_data_dir / "receipt_04.json"
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


@pytest.fixture
def mock_ocr_line():
    """Create a mock OCR line for testing."""

    def _create(text: str, confidence: float = 0.95, line_id: int = 1):
        return {
            "id": line_id,
            "text": text,
            "confidence": confidence,
            "words": [],
            "boundingBox": {"vertices": [{"x": 0, "y": 0}]},
        }

    return _create


@pytest.fixture
def mock_ocr_document(mock_ocr_line):
    """Create a mock OCR document for testing."""

    def _create(lines: list[str], confidence: float = 0.95):
        ocr_lines = [
            mock_ocr_line(text, confidence, i) for i, text in enumerate(lines)
        ]
        return {
            "apiVersion": "1.0",
            "confidence": confidence,
            "text": "\n".join(lines),
            "pages": [
                {
                    "id": 0,
                    "text": "\n".join(lines),
                    "confidence": confidence,
                    "width": 1000,
                    "height": 1000,
                    "words": [],
                    "lines": ocr_lines,
                }
            ],
        }

    return _create
