"""
크롤러 통합 테스트

전체 크롤링 파이프라인의 동작을 검증합니다.
실제 웹사이트 접속 없이 목 객체를 사용합니다.
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from bid_crawler.crawler import BidCrawler
from bid_crawler.config import CrawlerConfig
from bid_crawler.models.bid_notice import BidNotice, BidNoticeList, BidType, BidStatus


class TestBidCrawler:
    """BidCrawler 통합 테스트"""

    @pytest.fixture
    def crawler_config(self, tmp_path: Path) -> CrawlerConfig:
        """테스트용 설정"""
        config = CrawlerConfig(
            max_pages=1,
            max_items=5,
            log_level="DEBUG",
        )
        config.storage.data_dir = tmp_path / "data"
        config.storage.state_file = tmp_path / "state.json"
        config.log_file = tmp_path / "logs" / "test.log"
        return config

    @pytest.fixture
    def mock_list_data(self) -> BidNoticeList:
        """목 목록 데이터"""
        items = [
            BidNotice(
                bid_notice_id=f"TEST-{i}",
                title=f"테스트 공고 {i}",
                bid_type=BidType.GOODS,
                status=BidStatus.OPEN,
                detail_url=f"/detail/{i}",
            )
            for i in range(5)
        ]
        return BidNoticeList(
            items=items,
            total_count=5,
            current_page=1,
            total_pages=1,
            has_next=False,
        )

    @pytest.mark.asyncio
    async def test_crawler_initialization(self, crawler_config):
        """크롤러 초기화"""
        crawler = BidCrawler(crawler_config)

        assert crawler.config is not None
        assert crawler.state_manager is not None
        assert crawler.json_storage is not None

    @pytest.mark.asyncio
    async def test_callbacks(self, crawler_config):
        """콜백 등록"""
        crawler = BidCrawler(crawler_config)

        item_callback = MagicMock()
        page_callback = MagicMock()

        crawler.on_item_collected(item_callback)
        crawler.on_page_completed(page_callback)

        assert crawler._on_item_collected == item_callback
        assert crawler._on_page_completed == page_callback


class TestCrawlerWorkflow:
    """크롤러 워크플로우 테스트"""

    @pytest.fixture
    def crawler_config(self, tmp_path: Path) -> CrawlerConfig:
        """테스트용 설정"""
        config = CrawlerConfig(
            max_pages=2,
            max_items=10,
        )
        config.storage.data_dir = tmp_path / "data"
        config.storage.state_file = tmp_path / "state.json"
        return config

    def test_state_persistence(self, crawler_config, tmp_path):
        """상태 영속성"""
        crawler = BidCrawler(crawler_config)

        # 상태 초기화
        state = crawler.state_manager.initialize(crawler.config.run_id, resume=False)

        # 일부 작업 시뮬레이션
        crawler.state_manager.mark_collected("id1")
        crawler.state_manager.mark_collected("id2")
        crawler.state_manager.update_progress(page=2, index=5)
        crawler.state_manager.save()

        # 새 크롤러로 재시작
        new_crawler = BidCrawler(crawler_config)
        new_state = new_crawler.state_manager.initialize("new_run", resume=True)

        assert new_state.is_collected("id1")
        assert new_state.is_collected("id2")
        assert new_state.progress.current_page == 2
        assert new_state.progress.current_index == 5

    def test_storage_output(self, crawler_config, tmp_path, sample_bid_detail):
        """저장소 출력"""
        crawler_config.storage.output_format = "both"
        crawler = BidCrawler(crawler_config)

        # 데이터 저장 (리팩토링 후 json_storage.save() 직접 사용)
        crawler.json_storage.save(sample_bid_detail)
        if crawler.csv_storage:
            crawler.csv_storage.save(sample_bid_detail)
        crawler.json_storage.flush()

        # 파일 확인
        json_files = list(crawler_config.storage.data_dir.glob("*.json"))
        assert len(json_files) >= 1

        csv_files = list(crawler_config.storage.data_dir.glob("*.csv"))
        assert len(csv_files) >= 1


class TestEdgeCases:
    """엣지 케이스 테스트"""

    @pytest.fixture
    def config(self, tmp_path: Path) -> CrawlerConfig:
        config = CrawlerConfig()
        config.storage.data_dir = tmp_path / "data"
        config.storage.state_file = tmp_path / "state.json"
        return config

    def test_empty_list(self, config):
        """빈 목록 처리"""
        crawler = BidCrawler(config)
        # 빈 목록은 크롤링 종료를 의미

    def test_duplicate_handling(self, config):
        """중복 처리"""
        crawler = BidCrawler(config)

        # 첫 번째 수집
        assert crawler.state_manager.mark_collected("dup-id") is True

        # 중복 수집 시도
        assert crawler.state_manager.mark_collected("dup-id") is False
        assert crawler.state_manager.get_statistics().skipped_duplicates == 1

    def test_error_recovery(self, config):
        """오류 복구"""
        crawler = BidCrawler(config)

        # 오류 기록
        crawler.state_manager.record_error(
            "Test error",
            {"bid_id": "error-id", "url": "http://example.com"}
        )

        stats = crawler.state_manager.get_statistics()
        assert stats.errors == 1
        assert len(crawler.state_manager.state.failed_items) == 1
