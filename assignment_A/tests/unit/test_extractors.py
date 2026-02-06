"""Unit tests for extractor modules."""

import pytest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from weighing_parser.models.ocr_input import OCRDocument
from weighing_parser.extractors.document_type import DocumentTypeExtractor
from weighing_parser.extractors.date import DateExtractor
from weighing_parser.extractors.vehicle import VehicleExtractor
from weighing_parser.extractors.weights import WeightsExtractor
from weighing_parser.extractors.location import LocationExtractor
from weighing_parser.extractors.contact import ContactExtractor


class TestDocumentTypeExtractor:
    """Tests for DocumentTypeExtractor."""

    @pytest.fixture
    def extractor(self):
        return DocumentTypeExtractor()

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("계 량 증 명 서", "계량증명서"),
            ("** 계 량 확 인 서 **", "계량확인서"),
            ("계 량 증 명 표", "계량증명표"),
            ("* 계 그 표 *", "계표"),
        ],
    )
    def test_extract_document_type(self, extractor, mock_ocr_document, text, expected):
        """Test document type extraction."""
        doc_data = mock_ocr_document([text])
        document = OCRDocument(**doc_data)

        doc_type, confidence = extractor.extract(document)
        assert doc_type == expected
        assert confidence > 0


class TestDateExtractor:
    """Tests for DateExtractor."""

    @pytest.fixture
    def extractor(self):
        return DateExtractor()

    @pytest.mark.parametrize(
        "text,expected_date",
        [
            ("계량일자: 2026-02-02", "2026-02-02"),
            ("날 짜: 2026-02-02-00004", "2026-02-02"),
            ("일 시 2025-12-01", "2025-12-01"),
        ],
    )
    def test_extract_date(self, extractor, mock_ocr_document, text, expected_date):
        """Test date extraction."""
        from datetime import date

        doc_data = mock_ocr_document([text])
        document = OCRDocument(**doc_data)

        parsed_date, confidence = extractor.extract(document)
        assert parsed_date is not None
        assert parsed_date.isoformat() == expected_date
        assert confidence > 0


class TestVehicleExtractor:
    """Tests for VehicleExtractor."""

    @pytest.fixture
    def extractor(self):
        return VehicleExtractor()

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("차량번호: 8713", "8713"),
            ("차번호: 80구8713", "80구8713"),
            ("차량 No. 0580", "0580"),
        ],
    )
    def test_extract_vehicle(self, extractor, mock_ocr_document, text, expected):
        """Test vehicle number extraction."""
        doc_data = mock_ocr_document([text])
        document = OCRDocument(**doc_data)

        vehicle, confidence = extractor.extract(document)
        assert vehicle == expected
        assert confidence > 0


class TestWeightsExtractor:
    """Tests for WeightsExtractor."""

    @pytest.fixture
    def extractor(self):
        return WeightsExtractor()

    def test_extract_weights_sample_01(self, extractor, mock_ocr_document):
        """Test weight extraction from sample 01 format."""
        lines = [
            "총 중 량: 05:26:18 12,480 kg",
            "중 량: 05:36:01 7,470 kg",
            "실 중 량: 5,010 kg",
        ]
        doc_data = mock_ocr_document(lines)
        document = OCRDocument(**doc_data)

        total, tare, net, conf = extractor.extract(document)

        assert total is not None
        assert total.value_kg == 12480
        assert net is not None
        assert net.value_kg == 5010
        assert conf > 0

    def test_extract_weights_sample_02(self, extractor, mock_ocr_document):
        """Test weight extraction from sample 02 format (space-separated numbers)."""
        lines = [
            "총중량: 02:07 13 460 kg",
            "차중량: 02 : 13 7 560 kg",
            "실중량: 5 900 kg",
        ]
        doc_data = mock_ocr_document(lines)
        document = OCRDocument(**doc_data)

        total, tare, net, conf = extractor.extract(document)

        assert total is not None
        assert total.value_kg == 13460
        assert net is not None
        assert net.value_kg == 5900


class TestLocationExtractor:
    """Tests for LocationExtractor."""

    @pytest.fixture
    def extractor(self):
        return LocationExtractor()

    def test_extract_gps(self, extractor, mock_ocr_document):
        """Test GPS coordinate extraction."""
        lines = [
            "some text",
            "37.105317, 127.375673",
        ]
        doc_data = mock_ocr_document(lines)
        document = OCRDocument(**doc_data)

        gps, confidence = extractor.extract_gps(document)

        assert gps is not None
        assert gps.latitude == pytest.approx(37.105317)
        assert gps.longitude == pytest.approx(127.375673)

    def test_extract_address(self, extractor, mock_ocr_document):
        """Test address extraction."""
        lines = [
            "경기도 화성시 팔탄면 노하길454번길 23",
        ]
        doc_data = mock_ocr_document(lines)
        document = OCRDocument(**doc_data)

        address, confidence = extractor.extract_address(document)

        assert address is not None
        assert "화성시" in address


class TestContactExtractor:
    """Tests for ContactExtractor."""

    @pytest.fixture
    def extractor(self):
        return ContactExtractor()

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Tel) 031-354-7778", "031-354-7778"),
            ("TEL : (031)359-9127", "031-359-9127"),
        ],
    )
    def test_extract_phone(self, extractor, mock_ocr_document, text, expected):
        """Test phone number extraction."""
        doc_data = mock_ocr_document([text])
        document = OCRDocument(**doc_data)

        phone, confidence = extractor.extract(document)

        assert phone is not None
        assert expected.replace("-", "") in phone.replace("-", "")


# =============================================================================
# Edge Case Tests for Higher Coverage
# =============================================================================


class TestDocumentTypeExtractorEdgeCases:
    """Edge case tests for DocumentTypeExtractor."""

    @pytest.fixture
    def extractor(self):
        return DocumentTypeExtractor()

    def test_no_document_type_found(self, extractor, mock_ocr_document):
        """Test when no document type is found in text."""
        doc_data = mock_ocr_document(["일반 텍스트", "아무것도 없음"])
        document = OCRDocument(**doc_data)

        doc_type, confidence = extractor.extract(document)
        assert doc_type is None
        assert confidence == 0.0

    def test_empty_document(self, extractor, mock_ocr_document):
        """Test extraction from empty document."""
        doc_data = mock_ocr_document([])
        document = OCRDocument(**doc_data)

        doc_type, confidence = extractor.extract(document)
        assert doc_type is None
        assert confidence == 0.0

    def test_document_type_after_first_five_lines(self, extractor, mock_ocr_document):
        """Test document type appearing after first 5 lines is not found."""
        lines = ["line 1", "line 2", "line 3", "line 4", "line 5", "계 량 증 명 서"]
        doc_data = mock_ocr_document(lines)
        document = OCRDocument(**doc_data)

        doc_type, confidence = extractor.extract(document)
        # First 5 lines searched, 6th line not included
        assert doc_type is None

    def test_document_type_with_default_confidence(self, extractor, mock_ocr_document):
        """Test document type extraction returns default confidence when line not matched."""
        # Create document where pattern matches but line confidence lookup fails
        doc_data = mock_ocr_document(["계량증명서"])  # Without spaces, different from patterns
        document = OCRDocument(**doc_data)

        doc_type, confidence = extractor.extract(document)
        assert doc_type == "계량증명서"
        assert confidence > 0


class TestDateExtractorEdgeCases:
    """Edge case tests for DateExtractor."""

    @pytest.fixture
    def extractor(self):
        return DateExtractor()

    def test_no_date_found(self, extractor, mock_ocr_document):
        """Test when no date is found."""
        doc_data = mock_ocr_document(["텍스트만 있음", "날짜 없음"])
        document = OCRDocument(**doc_data)

        parsed_date, confidence = extractor.extract(document)
        assert parsed_date is None
        assert confidence == 0.0

    def test_date_on_next_line(self, extractor, mock_ocr_document):
        """Test date extraction when date is on the next line."""
        lines = ["계량일자:", "2026-03-15"]
        doc_data = mock_ocr_document(lines)
        document = OCRDocument(**doc_data)

        parsed_date, confidence = extractor.extract(document)
        assert parsed_date is not None
        assert parsed_date.isoformat() == "2026-03-15"

    def test_date_with_dot_format(self, extractor, mock_ocr_document):
        """Test date extraction with dot separator format."""
        doc_data = mock_ocr_document(["일시: 2026.01.15"])
        document = OCRDocument(**doc_data)

        parsed_date, confidence = extractor.extract(document)
        assert parsed_date is not None
        assert parsed_date.isoformat() == "2026-01-15"

    def test_date_with_slash_format(self, extractor, mock_ocr_document):
        """Test date extraction with slash separator format."""
        doc_data = mock_ocr_document(["날짜: 2026/01/15"])
        document = OCRDocument(**doc_data)

        parsed_date, confidence = extractor.extract(document)
        assert parsed_date is not None
        assert parsed_date.isoformat() == "2026-01-15"

    def test_extract_with_sequence_hyphen(self, extractor, mock_ocr_document):
        """Test date extraction with hyphen-separated sequence number."""
        doc_data = mock_ocr_document(["날 짜: 2026-02-02-00004"])
        document = OCRDocument(**doc_data)

        parsed_date, sequence, confidence = extractor.extract_with_sequence(document)
        assert parsed_date is not None
        assert parsed_date.isoformat() == "2026-02-02"
        assert sequence == "00004"

    def test_extract_with_sequence_space(self, extractor, mock_ocr_document):
        """Test date extraction with space-separated sequence number."""
        doc_data = mock_ocr_document(["계량일자: 2026-02-02 0016"])
        document = OCRDocument(**doc_data)

        parsed_date, sequence, confidence = extractor.extract_with_sequence(document)
        assert parsed_date is not None
        assert sequence == "0016"

    def test_extract_with_sequence_no_sequence(self, extractor, mock_ocr_document):
        """Test date extraction when there is no sequence number."""
        doc_data = mock_ocr_document(["일시: 2026-02-02"])
        document = OCRDocument(**doc_data)

        parsed_date, sequence, confidence = extractor.extract_with_sequence(document)
        assert parsed_date is not None
        assert sequence is None

    def test_extract_with_sequence_no_date(self, extractor, mock_ocr_document):
        """Test extract_with_sequence when no date is found."""
        doc_data = mock_ocr_document(["텍스트만 있음"])
        document = OCRDocument(**doc_data)

        parsed_date, sequence, confidence = extractor.extract_with_sequence(document)
        assert parsed_date is None
        assert sequence is None
        assert confidence == 0.0

    def test_fallback_to_full_text(self, extractor, mock_ocr_document):
        """Test fallback to searching full text when no label line found."""
        doc_data = mock_ocr_document(["2026-05-20"])  # Date without label
        document = OCRDocument(**doc_data)

        parsed_date, confidence = extractor.extract(document)
        assert parsed_date is not None
        assert parsed_date.isoformat() == "2026-05-20"


class TestVehicleExtractorEdgeCases:
    """Edge case tests for VehicleExtractor."""

    @pytest.fixture
    def extractor(self):
        return VehicleExtractor()

    def test_no_vehicle_number_found(self, extractor, mock_ocr_document):
        """Test when no vehicle number is found."""
        doc_data = mock_ocr_document(["텍스트만 있음", "차량 정보 없음"])
        document = OCRDocument(**doc_data)

        vehicle, confidence = extractor.extract(document)
        assert vehicle is None
        assert confidence == 0.0

    def test_vehicle_number_on_next_line(self, extractor, mock_ocr_document):
        """Test vehicle extraction when number is on next line."""
        lines = ["차량번호:", "12가3456"]
        doc_data = mock_ocr_document(lines)
        document = OCRDocument(**doc_data)

        vehicle, confidence = extractor.extract(document)
        # Pattern expects 2-3 digits + Korean char + 4 digits
        assert vehicle is not None

    def test_vehicle_number_3_digit_prefix(self, extractor, mock_ocr_document):
        """Test 3-digit prefix Korean plate format."""
        doc_data = mock_ocr_document(["차량번호: 123가4567"])
        document = OCRDocument(**doc_data)

        vehicle, confidence = extractor.extract(document)
        assert vehicle == "123가4567"

    def test_vehicle_label_with_no_prefix(self, extractor, mock_ocr_document):
        """Test vehicle label 'No' format."""
        doc_data = mock_ocr_document(["차량No. 9999"])
        document = OCRDocument(**doc_data)

        vehicle, confidence = extractor.extract(document)
        assert vehicle == "9999"

    def test_vehicle_label_not_found_no_extraction(self, extractor, mock_ocr_document):
        """Test no extraction when vehicle label not present."""
        doc_data = mock_ocr_document(["80구8713"])  # Number without label
        document = OCRDocument(**doc_data)

        vehicle, confidence = extractor.extract(document)
        assert vehicle is None  # No label found


class TestWeightsExtractorEdgeCases:
    """Edge case tests for WeightsExtractor."""

    @pytest.fixture
    def extractor(self):
        return WeightsExtractor()

    def test_no_weights_found(self, extractor, mock_ocr_document):
        """Test when no weights are found."""
        doc_data = mock_ocr_document(["텍스트만 있음", "중량 정보 없음"])
        document = OCRDocument(**doc_data)

        total, tare, net, conf = extractor.extract(document)
        assert total is None
        assert tare is None
        assert net is None
        assert conf == 0.0

    def test_partial_weights_only_total(self, extractor, mock_ocr_document):
        """Test extraction when only total weight is present."""
        doc_data = mock_ocr_document(["총중량: 10,000 kg"])
        document = OCRDocument(**doc_data)

        total, tare, net, conf = extractor.extract(document)
        assert total is not None
        assert total.value_kg == 10000
        assert tare is None
        assert net is None

    def test_partial_weights_only_net(self, extractor, mock_ocr_document):
        """Test extraction when only net weight is present."""
        doc_data = mock_ocr_document(["실중량: 5,000 kg"])
        document = OCRDocument(**doc_data)

        total, tare, net, conf = extractor.extract(document)
        assert total is None
        assert net is not None
        assert net.value_kg == 5000

    def test_weight_on_next_line(self, extractor, mock_ocr_document):
        """Test weight extraction when value is on next line."""
        lines = ["총중량:", "15,000 kg"]
        doc_data = mock_ocr_document(lines)
        document = OCRDocument(**doc_data)

        total, tare, net, conf = extractor.extract(document)
        assert total is not None
        assert total.value_kg == 15000

    def test_ocr_noise_label_variant(self, extractor, mock_ocr_document):
        """Test OCR noise label '품종명랑' (variant of 총중량)."""
        doc_data = mock_ocr_document(["품종명랑: 12,000 kg"])
        document = OCRDocument(**doc_data)

        total, tare, net, conf = extractor.extract(document)
        assert total is not None
        assert total.value_kg == 12000

    def test_legacy_extract_total(self, extractor, mock_ocr_document):
        """Test legacy extract_total method."""
        doc_data = mock_ocr_document(["총중량: 10,000 kg"])
        document = OCRDocument(**doc_data)

        total, conf = extractor.extract_total(document)
        assert total is not None
        assert total.value_kg == 10000

    def test_legacy_extract_tare(self, extractor, mock_ocr_document):
        """Test legacy extract_tare method."""
        doc_data = mock_ocr_document(["차중량: 5,000 kg"])
        document = OCRDocument(**doc_data)

        tare, conf = extractor.extract_tare(document)
        assert tare is not None
        assert tare.value_kg == 5000

    def test_legacy_extract_net(self, extractor, mock_ocr_document):
        """Test legacy extract_net method."""
        doc_data = mock_ocr_document(["실중량: 3,000 kg"])
        document = OCRDocument(**doc_data)

        net, conf = extractor.extract_net(document)
        assert net is not None
        assert net.value_kg == 3000

    def test_legacy_extract_total_not_found(self, extractor, mock_ocr_document):
        """Test legacy extract_total when not found."""
        doc_data = mock_ocr_document(["텍스트만"])
        document = OCRDocument(**doc_data)

        total, conf = extractor.extract_total(document)
        assert total is None
        assert conf == 0.0

    def test_weight_with_timestamp(self, extractor, mock_ocr_document):
        """Test weight extraction preserves timestamp."""
        doc_data = mock_ocr_document(["총중량: 05:26:18 12,480 kg"])
        document = OCRDocument(**doc_data)

        total, tare, net, conf = extractor.extract(document)
        assert total is not None
        assert total.timestamp == "05:26:18"

    def test_공차중량_label(self, extractor, mock_ocr_document):
        """Test 공차중량 (specific tare weight) label."""
        doc_data = mock_ocr_document(["공차중량: 6,000 kg"])
        document = OCRDocument(**doc_data)

        total, tare, net, conf = extractor.extract(document)
        assert tare is not None
        assert tare.value_kg == 6000


class TestLocationExtractorEdgeCases:
    """Edge case tests for LocationExtractor."""

    @pytest.fixture
    def extractor(self):
        return LocationExtractor()

    def test_no_gps_found(self, extractor, mock_ocr_document):
        """Test when no GPS coordinates are found."""
        doc_data = mock_ocr_document(["텍스트만 있음"])
        document = OCRDocument(**doc_data)

        gps, confidence = extractor.extract_gps(document)
        assert gps is None
        assert confidence == 0.0

    def test_gps_outside_korea_range(self, extractor, mock_ocr_document):
        """Test GPS outside Korea range is rejected."""
        # Tokyo coordinates (outside Korea range)
        doc_data = mock_ocr_document(["35.6762, 139.6503"])
        document = OCRDocument(**doc_data)

        gps, confidence = extractor.extract_gps(document)
        assert gps is None  # Longitude 139 is outside Korea (124-132)

    def test_no_address_found(self, extractor, mock_ocr_document):
        """Test when no address is found."""
        doc_data = mock_ocr_document(["숫자만 12345"])
        document = OCRDocument(**doc_data)

        address, confidence = extractor.extract_address(document)
        assert address is None
        assert confidence == 0.0

    def test_address_by_indicator_count(self, extractor, mock_ocr_document):
        """Test address detection by indicator count."""
        # Line with multiple address indicators but not matching pattern
        doc_data = mock_ocr_document(["서울 강남구 역삼동 123로"])
        document = OCRDocument(**doc_data)

        address, confidence = extractor.extract_address(document)
        assert address is not None
        assert "강남구" in address or "역삼동" in address

    def test_extract_both_gps_and_address(self, extractor, mock_ocr_document):
        """Test extract method returns both GPS and address."""
        lines = [
            "경기도 화성시 팔탄면 노하길454번길 23",
            "37.105317, 127.375673",
        ]
        doc_data = mock_ocr_document(lines)
        document = OCRDocument(**doc_data)

        gps, address, avg_conf = extractor.extract(document)
        assert gps is not None
        assert address is not None
        assert avg_conf > 0

    def test_extract_neither_found(self, extractor, mock_ocr_document):
        """Test extract method when neither GPS nor address found."""
        doc_data = mock_ocr_document(["아무것도 없음"])
        document = OCRDocument(**doc_data)

        gps, address, avg_conf = extractor.extract(document)
        assert gps is None
        assert address is None
        assert avg_conf == 0.0

    def test_address_various_provinces(self, extractor, mock_ocr_document):
        """Test address extraction for various Korean provinces."""
        provinces = [
            "서울특별시 강남구 테헤란로 123",
            "부산광역시 해운대구 우동 456",
            "충청남도 천안시 동남구 신부동 789",
        ]
        for province in provinces:
            doc_data = mock_ocr_document([province])
            document = OCRDocument(**doc_data)

            address, confidence = extractor.extract_address(document)
            assert address is not None, f"Failed for: {province}"


class TestContactExtractorEdgeCases:
    """Edge case tests for ContactExtractor."""

    @pytest.fixture
    def extractor(self):
        return ContactExtractor()

    def test_no_phone_found(self, extractor, mock_ocr_document):
        """Test when no phone number is found."""
        doc_data = mock_ocr_document(["텍스트만 있음"])
        document = OCRDocument(**doc_data)

        phone, confidence = extractor.extract(document)
        assert phone is None
        assert confidence == 0.0

    def test_fax_extraction(self, extractor, mock_ocr_document):
        """Test fax number extraction."""
        doc_data = mock_ocr_document(["Fax: 031-123-4567"])
        document = OCRDocument(**doc_data)

        fax, confidence = extractor.extract_fax(document)
        assert fax is not None
        assert "031" in fax

    def test_fax_not_found(self, extractor, mock_ocr_document):
        """Test when fax number is not found."""
        doc_data = mock_ocr_document(["Tel: 031-123-4567"])
        document = OCRDocument(**doc_data)

        fax, confidence = extractor.extract_fax(document)
        assert fax is None

    def test_phone_korean_label(self, extractor, mock_ocr_document):
        """Test phone extraction with Korean label."""
        doc_data = mock_ocr_document(["전화: 02-1234-5678"])
        document = OCRDocument(**doc_data)

        phone, confidence = extractor.extract(document)
        assert phone is not None

    def test_phone_10_digit_format(self, extractor, mock_ocr_document):
        """Test 10-digit phone number normalization."""
        doc_data = mock_ocr_document(["Tel) 0312345678"])
        document = OCRDocument(**doc_data)

        phone, confidence = extractor.extract(document)
        assert phone is not None
        # Should be normalized to 031-234-5678 format

    def test_phone_11_digit_format(self, extractor, mock_ocr_document):
        """Test 11-digit phone number normalization."""
        doc_data = mock_ocr_document(["Tel) 01012345678"])
        document = OCRDocument(**doc_data)

        phone, confidence = extractor.extract(document)
        assert phone is not None
        # Should be normalized to 010-1234-5678 format

    def test_fax_korean_label(self, extractor, mock_ocr_document):
        """Test fax extraction with Korean label."""
        doc_data = mock_ocr_document(["팩스: 02-9876-5432"])
        document = OCRDocument(**doc_data)

        fax, confidence = extractor.extract_fax(document)
        assert fax is not None


class TestBaseExtractorEdgeCases:
    """Edge case tests for BaseExtractor helper methods."""

    @pytest.fixture
    def extractor(self):
        return DocumentTypeExtractor()  # Use concrete implementation

    def test_find_line_containing_case_insensitive(self, extractor, mock_ocr_document):
        """Test case-insensitive line search."""
        doc_data = mock_ocr_document(["HELLO WORLD", "test line"])
        document = OCRDocument(**doc_data)
        lines = document.get_lines()

        result = extractor.find_line_containing(
            lines, ["hello"], case_insensitive=True
        )
        assert result is not None
        assert result.text == "HELLO WORLD"

    def test_find_line_containing_case_sensitive_no_match(self, extractor, mock_ocr_document):
        """Test case-sensitive search doesn't match different case."""
        doc_data = mock_ocr_document(["HELLO WORLD"])
        document = OCRDocument(**doc_data)
        lines = document.get_lines()

        result = extractor.find_line_containing(
            lines, ["hello"], case_insensitive=False
        )
        assert result is None

    def test_find_all_lines_containing(self, extractor, mock_ocr_document):
        """Test finding all matching lines."""
        doc_data = mock_ocr_document(["test line 1", "other line", "test line 2"])
        document = OCRDocument(**doc_data)
        lines = document.get_lines()

        results = extractor.find_all_lines_containing(lines, ["test"])
        assert len(results) == 2

    def test_find_all_lines_containing_case_insensitive(self, extractor, mock_ocr_document):
        """Test case-insensitive search for all matching lines."""
        doc_data = mock_ocr_document(["TEST line", "other", "test LINE"])
        document = OCRDocument(**doc_data)
        lines = document.get_lines()

        results = extractor.find_all_lines_containing(
            lines, ["test"], case_insensitive=True
        )
        assert len(results) == 2

    def test_get_line_index_not_found(self, extractor, mock_ocr_document):
        """Test get_line_index returns -1 when line not found."""
        doc_data = mock_ocr_document(["line 1", "line 2"])
        document = OCRDocument(**doc_data)
        lines = document.get_lines()

        # Create a fake line that doesn't exist
        from weighing_parser.models.ocr_input import Line
        fake_line = Line(id=999, text="fake", confidence=0.9, words=[], boundingBox={"vertices": []})

        idx = extractor.get_line_index(lines, fake_line)
        assert idx == -1

    def test_get_next_line_at_end(self, extractor, mock_ocr_document):
        """Test get_next_line returns None at end of document."""
        doc_data = mock_ocr_document(["line 1", "line 2"])
        document = OCRDocument(**doc_data)
        lines = document.get_lines()

        # Get next line after the last line
        last_line = lines[-1]
        next_line = extractor.get_next_line(lines, last_line)
        assert next_line is None

    def test_get_next_line_success(self, extractor, mock_ocr_document):
        """Test get_next_line returns correct next line."""
        doc_data = mock_ocr_document(["line 1", "line 2", "line 3"])
        document = OCRDocument(**doc_data)
        lines = document.get_lines()

        first_line = lines[0]
        next_line = extractor.get_next_line(lines, first_line)
        assert next_line is not None
        assert next_line.text == "line 2"
