"""
데이터 모델 테스트

BidNotice, BidNoticeDetail, CrawlState 모델의 동작을 검증합니다.
"""

import pytest
from datetime import datetime

from bid_crawler.models.bid_notice import (
    BidNotice,
    BidNoticeDetail,
    BidNoticeList,
    BidType,
    BidStatus,
)
from bid_crawler.models.crawl_state import (
    CrawlState,
    CrawlProgress,
    CrawlStatistics,
)


class TestBidNotice:
    """BidNotice 모델 테스트"""

    def test_create_minimal(self):
        """최소 필수 필드로 생성"""
        notice = BidNotice(
            bid_notice_id="12345",
            title="테스트 공고",
        )
        assert notice.bid_notice_id == "12345"
        assert notice.title == "테스트 공고"
        assert notice.bid_type == BidType.OTHER
        assert notice.status == BidStatus.UNKNOWN

    def test_create_full(self, sample_bid_notice):
        """모든 필드로 생성"""
        assert sample_bid_notice.bid_notice_id == "20240115-001"
        assert sample_bid_notice.bid_type == BidType.GOODS
        assert sample_bid_notice.status == BidStatus.OPEN
        assert sample_bid_notice.estimated_price == 100000000

    def test_json_serialization(self, sample_bid_notice):
        """JSON 직렬화"""
        json_data = sample_bid_notice.model_dump_json()
        assert "20240115-001" in json_data
        assert "테스트 입찰공고" in json_data


class TestBidNoticeDetail:
    """BidNoticeDetail 모델 테스트"""

    def test_inherits_bid_notice(self, sample_bid_detail):
        """BidNotice 상속 확인"""
        assert isinstance(sample_bid_detail, BidNotice)
        assert sample_bid_detail.bid_notice_id == "20240115-001"

    def test_detail_fields(self, sample_bid_detail):
        """상세 필드 확인"""
        assert sample_bid_detail.bid_method == "일반경쟁입찰"
        assert sample_bid_detail.contact_person == "홍길동"
        assert len(sample_bid_detail.attachments) == 2

    def test_crawl_metadata(self, sample_bid_detail):
        """크롤링 메타데이터"""
        assert sample_bid_detail.crawl_success is True
        assert sample_bid_detail.detail_crawled_at is not None


class TestBidNoticeList:
    """BidNoticeList 모델 테스트"""

    def test_empty_list(self):
        """빈 목록"""
        bid_list = BidNoticeList()
        assert bid_list.items == []
        assert bid_list.total_count == 0
        assert bid_list.has_next is False

    def test_with_items(self, sample_notices):
        """항목이 있는 목록"""
        bid_list = BidNoticeList(
            items=sample_notices,
            total_count=100,
            current_page=1,
            total_pages=10,
            has_next=True,
        )
        assert len(bid_list.items) == 5
        assert bid_list.has_next is True


class TestCrawlState:
    """CrawlState 모델 테스트"""

    def test_create_default(self):
        """기본 상태 생성"""
        state = CrawlState(run_id="test")
        assert state.run_id == "test"
        assert state.is_running is False
        assert state.is_completed is False
        assert len(state.collected_ids) == 0

    def test_mark_collected(self, crawl_state):
        """수집 완료 표시"""
        # 새 ID
        assert crawl_state.mark_collected("new_id") is True
        assert "new_id" in crawl_state.collected_ids

        # 중복 ID
        assert crawl_state.mark_collected("id1") is False
        assert crawl_state.statistics.skipped_duplicates == 1

    def test_is_collected(self, crawl_state):
        """수집 여부 확인"""
        assert crawl_state.is_collected("id1") is True
        assert crawl_state.is_collected("unknown") is False

    def test_record_error(self, crawl_state):
        """오류 기록"""
        initial_errors = crawl_state.statistics.errors
        crawl_state.record_error("Test error", {"id": "test"})

        assert crawl_state.statistics.errors == initial_errors + 1
        assert crawl_state.last_error == "Test error"
        assert len(crawl_state.failed_items) == 1

    def test_update_progress(self, crawl_state):
        """진행 상황 업데이트"""
        crawl_state.update_progress(page=5, index=3)
        assert crawl_state.progress.current_page == 5
        assert crawl_state.progress.current_index == 3

    def test_complete_page(self, crawl_state):
        """페이지 완료"""
        crawl_state.complete_page(5)
        assert crawl_state.progress.last_completed_page == 5
        assert crawl_state.progress.current_index == 0

    def test_mark_completed(self, crawl_state):
        """크롤링 완료"""
        crawl_state.mark_completed()
        assert crawl_state.is_completed is True
        assert crawl_state.is_running is False


class TestCrawlStatistics:
    """CrawlStatistics 모델 테스트"""

    def test_success_rate_no_data(self):
        """데이터 없을 때 성공률"""
        stats = CrawlStatistics()
        assert stats.success_rate == 100.0

    def test_success_rate_with_errors(self):
        """오류 있을 때 성공률"""
        stats = CrawlStatistics(
            total_collected=80,
            errors=20,
        )
        assert stats.success_rate == 80.0
