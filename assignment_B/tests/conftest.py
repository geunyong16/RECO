"""
pytest 설정 및 공통 픽스처

테스트에서 사용되는 공통 설정과 목 객체를 정의합니다.
Decimal 타입을 사용하도록 업데이트되었습니다.
"""

import pytest
import asyncio
from pathlib import Path
from typing import AsyncGenerator
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from bid_crawler.config import CrawlerConfig, BrowserConfig
from bid_crawler.models.bid_notice import BidNotice, BidNoticeDetail, BidType, BidStatus
from bid_crawler.models.crawl_state import CrawlState, CrawlProgress, CrawlStatistics


# === Event Loop 설정 ===

@pytest.fixture(scope="session")
def event_loop():
    """세션 범위 이벤트 루프"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# === 설정 픽스처 ===

@pytest.fixture
def test_config(tmp_path: Path) -> CrawlerConfig:
    """테스트용 크롤러 설정"""
    return CrawlerConfig(
        max_pages=2,
        max_items=10,
        log_level="DEBUG",
        browser=BrowserConfig(
            headless=True,
            timeout=10000,
        ),
    )


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """임시 데이터 디렉토리"""
    data = tmp_path / "data"
    data.mkdir()
    return data


# === 모델 픽스처 (Decimal 사용) ===

@pytest.fixture
def sample_bid_notice() -> BidNotice:
    """샘플 입찰공고 (목록 항목) - Decimal 사용"""
    return BidNotice(
        bid_notice_id="20240115-001",
        title="테스트 입찰공고",
        bid_type=BidType.GOODS,
        status=BidStatus.OPEN,
        organization="테스트 기관",
        deadline=datetime(2024, 1, 31, 17, 0),
        estimated_price=Decimal("100000000"),  # int -> Decimal
        detail_url="/detail?id=20240115-001",
        crawled_at=datetime.now(),
    )


@pytest.fixture
def sample_bid_detail(sample_bid_notice: BidNotice) -> BidNoticeDetail:
    """샘플 입찰공고 상세 - Decimal 사용"""
    data = sample_bid_notice.model_dump()
    # 추가 필드 설정
    data["base_price"] = Decimal("95000000")
    data["demand_organization"] = "수요기관"
    data["bid_method"] = "일반경쟁입찰"
    data["contract_method"] = "총액계약"
    data["qualification"] = "중소기업자"
    data["region"] = "서울특별시"
    data["contact_department"] = "구매팀"
    data["contact_person"] = "홍길동"
    data["contact_phone"] = "02-1234-5678"
    data["attachments"] = ["공고문.pdf", "규격서.hwp"]
    data["detail_crawled_at"] = datetime.now()
    data["crawl_success"] = True
    return BidNoticeDetail(**data)


@pytest.fixture
def sample_notices() -> list:
    """여러 샘플 공고 - Decimal 사용"""
    notices = []
    for i in range(5):
        notices.append(BidNotice(
            bid_notice_id=f"2024011{i}-001",
            title=f"테스트 입찰공고 {i+1}",
            bid_type=BidType.GOODS if i % 2 == 0 else BidType.SERVICE,
            status=BidStatus.OPEN,
            organization=f"기관 {i+1}",
            estimated_price=Decimal(str(10000000 * (i + 1))),  # Decimal 사용
        ))
    return notices


@pytest.fixture
def crawl_state() -> CrawlState:
    """샘플 크롤링 상태"""
    return CrawlState(
        run_id="test_run_001",
        is_running=True,
        progress=CrawlProgress(
            current_page=3,
            current_index=5,
            total_pages=10,
        ),
        statistics=CrawlStatistics(
            total_collected=25,
            list_collected=30,
            detail_collected=25,
            errors=5,
        ),
        collected_ids={"id1", "id2", "id3"},
    )


# === 도메인 테스트용 픽스처 ===

@pytest.fixture
def valuable_bid() -> BidNotice:
    """가치있는 입찰 (1억 이상) - 도메인 행동 테스트용"""
    return BidNotice(
        bid_notice_id="valuable-001",
        title="고가 입찰",
        estimated_price=Decimal("500000000"),  # 5억
        status=BidStatus.OPEN,
        deadline=datetime.now() + timedelta(days=30),  # 미래
    )


@pytest.fixture
def expired_bid() -> BidNotice:
    """마감된 입찰 - 도메인 행동 테스트용"""
    return BidNotice(
        bid_notice_id="expired-001",
        title="마감 입찰",
        status=BidStatus.OPEN,
        deadline=datetime(2020, 1, 1),  # 과거
    )


@pytest.fixture
def low_value_bid() -> BidNotice:
    """저가 입찰 - 도메인 행동 테스트용"""
    return BidNotice(
        bid_notice_id="low-001",
        title="저가 입찰",
        estimated_price=Decimal("50000000"),  # 5천만
        status=BidStatus.OPEN,
        deadline=datetime.now() + timedelta(days=30),
    )


@pytest.fixture
def no_price_bid() -> BidNotice:
    """가격 없는 입찰 - 도메인 행동 테스트용"""
    return BidNotice(
        bid_notice_id="no-price-001",
        title="가격 미정",
        status=BidStatus.OPEN,
    )


# === Repository Mock ===

@pytest.fixture
def mock_repository() -> MagicMock:
    """BidRepository Mock"""
    repo = MagicMock()
    repo.save = MagicMock(return_value=True)
    repo.save_batch = MagicMock(return_value=5)
    repo.exists = MagicMock(return_value=False)
    repo.find_by_id = MagicMock(return_value=None)
    repo.find_all = MagicMock(return_value=[])
    repo.count = MagicMock(return_value=0)
    repo.flush = MagicMock(return_value=True)
    repo.close = MagicMock()
    return repo


# === 목 객체 픽스처 ===

@pytest.fixture
def mock_page() -> AsyncMock:
    """Playwright 페이지 목 객체"""
    page = AsyncMock()

    # 기본 메서드 설정
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.query_selector_all = AsyncMock(return_value=[])
    page.content = AsyncMock(return_value="<html></html>")
    page.url = "https://test.example.com"
    page.go_back = AsyncMock()
    page.close = AsyncMock()

    return page


@pytest.fixture
def mock_browser_manager(mock_page: AsyncMock) -> MagicMock:
    """브라우저 매니저 목 객체"""
    manager = MagicMock()
    manager.start = AsyncMock()
    manager.stop = AsyncMock()
    manager.new_page = AsyncMock(return_value=mock_page)

    # 컨텍스트 매니저
    manager.__aenter__ = AsyncMock(return_value=manager)
    manager.__aexit__ = AsyncMock()

    return manager


# === 유틸리티 함수 ===

def create_mock_element(text: str = "", href: str = "") -> AsyncMock:
    """목 HTML 요소 생성"""
    element = AsyncMock()
    element.text_content = AsyncMock(return_value=text)
    element.get_attribute = AsyncMock(return_value=href)
    element.inner_html = AsyncMock(return_value=f"<span>{text}</span>")
    element.click = AsyncMock()
    element.fill = AsyncMock()
    return element


def create_mock_table_row(cells: list) -> AsyncMock:
    """목 테이블 행 생성"""
    row = AsyncMock()
    mock_cells = [create_mock_element(text=cell) for cell in cells]
    row.query_selector_all = AsyncMock(return_value=mock_cells)
    return row
