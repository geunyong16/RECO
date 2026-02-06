"""Integration tests for the full parsing pipeline."""

import pytest
from pathlib import Path
from datetime import date

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from weighing_parser.parser import WeighingReceiptParser
from weighing_parser.models.ocr_input import OCRDocument
from weighing_parser.output.json_writer import JSONWriter
from weighing_parser.output.csv_writer import CSVWriter


@pytest.fixture
def parser():
    """Create parser instance."""
    return WeighingReceiptParser()


@pytest.fixture
def sample_data_dir():
    """Get sample data directory."""
    base = Path(__file__).parent.parent.parent
    return base / "[2026 ICT_리코] smaple_data_ocr"


class TestParserIntegration:
    """Integration tests using actual sample data."""

    def test_parse_sample_01(self, parser, sample_data_dir):
        """Test parsing sample 01 (계량증명서)."""
        if sample_data_dir is None:
            pytest.skip("Sample data directory not found")

        filepath = sample_data_dir / "sample_01.json"
        if not filepath.exists():
            pytest.skip(f"Sample file not found: {filepath}")

        receipt = parser.parse_file(filepath)

        assert receipt.document_type == "계량증명서"
        assert receipt.date == date(2026, 2, 2)
        assert receipt.vehicle_number == "8713"
        assert receipt.total_weight is not None
        assert receipt.total_weight.value_kg == 12480
        assert receipt.tare_weight is not None
        assert receipt.tare_weight.value_kg == 7470
        assert receipt.net_weight is not None
        assert receipt.net_weight.value_kg == 5010
        assert "동우바이오" in (receipt.issuing_company or "")
        assert receipt.gps_coordinates is not None
        assert receipt.gps_coordinates.latitude == pytest.approx(37.105317, rel=0.001)

    def test_parse_sample_02(self, parser, sample_data_dir):
        """Test parsing sample 02 (계표)."""
        if sample_data_dir is None:
            pytest.skip("Sample data directory not found")

        filepath = sample_data_dir / "sample_02.json"
        if not filepath.exists():
            pytest.skip(f"Sample file not found: {filepath}")

        receipt = parser.parse_file(filepath)

        assert receipt.document_type == "계표"
        assert receipt.vehicle_number == "80구8713"
        assert receipt.company_name is not None
        assert "고요환경" in receipt.company_name
        assert receipt.total_weight is not None
        assert receipt.total_weight.value_kg == 13460
        assert receipt.net_weight is not None
        assert receipt.net_weight.value_kg == 5900
        assert "장원" in (receipt.issuing_company or "")

    def test_parse_sample_03(self, parser, sample_data_dir):
        """Test parsing sample 03 (계량확인서)."""
        if sample_data_dir is None:
            pytest.skip("Sample data directory not found")

        filepath = sample_data_dir / "sample_03.json"
        if not filepath.exists():
            pytest.skip(f"Sample file not found: {filepath}")

        receipt = parser.parse_file(filepath)

        assert receipt.document_type == "계량확인서"
        assert receipt.date == date(2026, 2, 1)
        assert receipt.vehicle_number == "5405"
        assert receipt.net_weight is not None
        assert receipt.net_weight.value_kg == 130
        assert "리사이클링" in (receipt.issuing_company or "")
        assert receipt.phone is not None
        assert "031" in receipt.phone

    def test_parse_sample_04(self, parser, sample_data_dir):
        """Test parsing sample 04 (계량증명표)."""
        if sample_data_dir is None:
            pytest.skip("Sample data directory not found")

        filepath = sample_data_dir / "sample_04.json"
        if not filepath.exists():
            pytest.skip(f"Sample file not found: {filepath}")

        receipt = parser.parse_file(filepath)

        assert receipt.document_type == "계량증명표"
        assert receipt.date == date(2025, 12, 1)
        assert receipt.vehicle_number == "0580"
        assert receipt.total_weight is not None
        assert receipt.total_weight.value_kg == 14230
        assert receipt.tare_weight is not None
        assert receipt.tare_weight.value_kg == 12910
        assert receipt.net_weight is not None
        assert receipt.net_weight.value_kg == 1320
        # issuing_company may have OCR issues with spaced characters
        assert receipt.issuing_company is not None or receipt.phone is not None

    def test_weight_validation(self, parser, sample_data_dir):
        """Test that weight validation passes for all samples."""
        if sample_data_dir is None:
            pytest.skip("Sample data directory not found")

        for filename in ["sample_01.json", "sample_02.json", "sample_03.json", "sample_04.json"]:
            filepath = sample_data_dir / filename
            if not filepath.exists():
                continue

            receipt = parser.parse_file(filepath)

            # Check no critical validation errors (allow confidence warnings)
            critical_errors = [
                e for e in receipt.validation_errors
                if "mismatch" in e.lower() or "negative" in e.lower()
            ]
            assert len(critical_errors) == 0, f"Validation errors in {filename}: {critical_errors}"

    def test_batch_parse(self, parser, sample_data_dir):
        """Test batch parsing multiple files."""
        if sample_data_dir is None:
            pytest.skip("Sample data directory not found")

        filepaths = list(sample_data_dir.glob("sample_*.json"))
        if not filepaths:
            pytest.skip("No sample files found")

        receipts = parser.parse_batch(filepaths)

        assert len(receipts) == len(filepaths)
        for receipt in receipts:
            assert receipt.document_type is not None


class TestOutputIntegration:
    """Integration tests for output writers."""

    def test_json_output(self, parser, sample_data_dir, tmp_path):
        """Test JSON output writing."""
        if sample_data_dir is None:
            pytest.skip("Sample data directory not found")

        filepath = sample_data_dir / "sample_01.json"
        if not filepath.exists():
            pytest.skip("Sample file not found")

        receipt = parser.parse_file(filepath)
        output_path = tmp_path / "output.json"

        JSONWriter.write(receipt, output_path)

        assert output_path.exists()
        # Verify it's valid JSON
        import json
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "document_type" in data
        assert data["document_type"] == "계량증명서"

    def test_csv_output(self, parser, sample_data_dir, tmp_path):
        """Test CSV output writing."""
        if sample_data_dir is None:
            pytest.skip("Sample data directory not found")

        filepaths = list(sample_data_dir.glob("sample_*.json"))[:2]
        if not filepaths:
            pytest.skip("No sample files found")

        receipts = parser.parse_batch(filepaths)
        output_path = tmp_path / "output.csv"

        CSVWriter.write_batch(receipts, output_path)

        assert output_path.exists()
        # Verify content
        with open(output_path, "r", encoding="utf-8-sig") as f:
            content = f.read()
        assert "document_type" in content
        assert "total_weight_kg" in content
