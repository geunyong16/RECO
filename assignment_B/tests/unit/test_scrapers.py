"""
스크래퍼 모듈 테스트

BaseScraper, ListScraper, DetailScraper의 동작을 검증합니다.
"""

import pytest
from unittest.mock import AsyncMock
from datetime import datetime

from bid_crawler.scrapers.base import BaseScraper
from bid_crawler.scrapers.list_scraper import ListScraper
from bid_crawler.scrapers.detail_scraper import DetailScraper
from bid_crawler.models.bid_notice import BidType, BidStatus


class TestBaseScraper:
    """BaseScraper 테스트"""

    def test_clean_text(self, mock_page):
        """텍스트 정리"""
        # 직접 인스턴스화 불가 (추상 클래스)
        scraper = ListScraper(mock_page)

        assert scraper._clean_text("  hello  world  ") == "hello world"
        assert scraper._clean_text("line1\n\nline2") == "line1 line2"
        assert scraper._clean_text(None) == ""

    def test_parse_price(self, mock_page):
        """가격 파싱"""
        scraper = ListScraper(mock_page)

        assert scraper.parse_price("123,456,789원") == 123456789
        assert scraper.parse_price("₩ 1,000,000") == 1000000
        assert scraper.parse_price("가격미정") is None
        assert scraper.parse_price("") is None

    def test_parse_datetime(self, mock_page):
        """날짜 파싱"""
        scraper = ListScraper(mock_page)

        # 다양한 형식 테스트
        dt = scraper.parse_datetime("2024-01-15 14:30")
        assert dt == datetime(2024, 1, 15, 14, 30)

        dt = scraper.parse_datetime("2024.01.15")
        assert dt == datetime(2024, 1, 15)

        dt = scraper.parse_datetime("2024년 01월 15일 14시 30분")
        assert dt == datetime(2024, 1, 15, 14, 30)

        assert scraper.parse_datetime("") is None
        assert scraper.parse_datetime("잘못된 날짜") is None

    def test_extract_bid_id(self, mock_page):
        """공고번호 추출"""
        scraper = ListScraper(mock_page)

        assert scraper.extract_bid_id("20240115-001") == "20240115-001"
        assert scraper.extract_bid_id("2024011500001") == "2024011500001"
        assert scraper.extract_bid_id("공고번호: 20240115-001") == "20240115-001"


class TestListScraper:
    """ListScraper 테스트"""

    def test_map_bid_type(self, mock_page):
        """입찰 유형 매핑"""
        scraper = ListScraper(mock_page)

        assert scraper._map_bid_type("물품구매") == BidType.GOODS
        assert scraper._map_bid_type("용역") == BidType.SERVICE
        assert scraper._map_bid_type("공사") == BidType.CONSTRUCTION
        assert scraper._map_bid_type("기타") == BidType.OTHER

    def test_map_status(self, mock_page):
        """상태 매핑"""
        scraper = ListScraper(mock_page)

        assert scraper._map_status("공고중") == BidStatus.OPEN
        assert scraper._map_status("마감") == BidStatus.CLOSED
        assert scraper._map_status("취소") == BidStatus.CANCELLED
        assert scraper._map_status("알수없음") == BidStatus.UNKNOWN

    @pytest.mark.asyncio
    async def test_extract_title_and_url(self, mock_page):
        """제목 및 URL 추출"""
        from tests.conftest import create_mock_element

        scraper = ListScraper(mock_page)

        # 링크가 있는 셀
        cell = AsyncMock()
        link = create_mock_element(text="테스트 공고", href="/detail?id=123")
        cell.query_selector = AsyncMock(return_value=link)

        title, url = await scraper._extract_title_and_url([None, None, cell])

        assert title == "테스트 공고"
        assert url == "/detail?id=123"


class TestDetailScraper:
    """DetailScraper 테스트"""

    def test_map_bid_type(self, mock_page):
        """입찰 유형 매핑"""
        scraper = DetailScraper(mock_page)

        assert scraper._map_bid_type("물품") == BidType.GOODS
        assert scraper._map_bid_type("용역계약") == BidType.SERVICE

    def test_map_status(self, mock_page):
        """상태 매핑"""
        scraper = DetailScraper(mock_page)

        assert scraper._map_status("진행중") == BidStatus.OPEN
        assert scraper._map_status("마감됨") == BidStatus.CLOSED

    def test_build_detail_from_raw(self, mock_page, sample_bid_notice):
        """원시 데이터에서 상세 객체 생성"""
        scraper = DetailScraper(mock_page)

        raw_data = {
            "공고번호": "20240115-001",
            "공고명": "테스트 공고",
            "입찰방식": "일반경쟁",
            "담당자": "홍길동",
            "연락처": "02-1234-5678",
        }

        detail = scraper._build_detail(raw_data, sample_bid_notice)

        assert detail.bid_notice_id == "20240115-001"
        assert detail.bid_method == "일반경쟁"
        assert detail.contact_person == "홍길동"
        assert detail.contact_phone == "02-1234-5678"
