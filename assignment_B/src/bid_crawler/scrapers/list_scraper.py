"""
목록 페이지 스크래퍼

입찰공고 목록 페이지에서 공고 목록을 추출합니다.
"""

import asyncio
import re
from typing import List, Optional, Tuple
from datetime import datetime

from playwright.async_api import Page

from bid_crawler.scrapers.base import BaseScraper, ScraperError
from bid_crawler.models.bid_notice import (
    BidNotice,
    BidNoticeList,
    BidType,
    BidStatus,
)
from bid_crawler.utils.logger import get_logger

logger = get_logger(__name__)


class ListScraper(BaseScraper):
    """
    입찰공고 목록 스크래퍼

    나라장터 입찰공고 목록 페이지를 파싱하여
    BidNotice 객체 리스트를 반환합니다.
    """

    # 나라장터 선택자 (실제 사이트에 맞게 조정 필요)
    SELECTORS = {
        # 테이블 관련
        "table": "table.list_table, table.tb_list, #resultList table",
        "rows": "table tbody tr, table.list_table tr:not(:first-child)",
        "no_data": ".no_data, .nodata, td[colspan]",

        # 페이지네이션
        "pagination": ".pagination, .paging, #paging",
        "page_links": ".pagination a, .paging a",
        "current_page": ".pagination .on, .paging .current",
        "next_page": ".pagination .next, .paging .next, a[title='다음']",
        "total_count": ".total_count, .count, #totalCnt",

        # 목록 항목 (행 내부 셀)
        "bid_id": "td:nth-child(2), td.bid_no",
        "title": "td:nth-child(3) a, td.title a, td a.title",
        "organization": "td:nth-child(4), td.org",
        "bid_type": "td:nth-child(5), td.type",
        "status": "td:nth-child(6), td.status",
        "deadline": "td:nth-child(7), td.deadline",
        "price": "td:nth-child(8), td.price",
    }

    # 입찰 유형 매핑
    BID_TYPE_MAP = {
        "물품": BidType.GOODS,
        "용역": BidType.SERVICE,
        "공사": BidType.CONSTRUCTION,
        "외자": BidType.FOREIGN,
    }

    # 상태 매핑
    STATUS_MAP = {
        "공고중": BidStatus.OPEN,
        "진행중": BidStatus.OPEN,
        "마감": BidStatus.CLOSED,
        "마감됨": BidStatus.CLOSED,
        "취소": BidStatus.CANCELLED,
        "연기": BidStatus.POSTPONED,
        "재공고": BidStatus.REBID,
    }

    async def scrape(self) -> BidNoticeList:
        """
        현재 페이지의 입찰공고 목록 스크래핑

        Returns:
            BidNoticeList: 공고 목록 및 페이지 정보
        """
        # 테이블 로드 대기
        await self._wait_for_table()

        # 공고 목록 추출
        notices = await self._extract_notices()

        # 페이지 정보 추출
        total_count, current_page, total_pages = await self._extract_pagination_info()

        return BidNoticeList(
            items=notices,
            total_count=total_count,
            current_page=current_page,
            total_pages=total_pages,
            has_next=current_page < total_pages,
        )

    async def _wait_for_table(self, timeout: int = 10000) -> None:
        """테이블 로드 대기"""
        try:
            # 여러 선택자 중 하나라도 로드되면 진행
            selectors = self.SELECTORS["table"].split(", ")
            for selector in selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=timeout // len(selectors))
                    self.logger.debug(f"테이블 로드됨: {selector}")
                    return
                except Exception:
                    continue

            # 데이터 없음 메시지 확인
            if await self.exists(self.SELECTORS["no_data"], timeout=2000):
                self.logger.info("검색 결과가 없습니다")
                return

            raise ScraperError("테이블을 찾을 수 없습니다", self.SELECTORS["table"])

        except ScraperError:
            raise
        except Exception as e:
            raise ScraperError(f"테이블 로드 실패: {e}")

    async def _extract_notices(self) -> List[BidNotice]:
        """목록에서 공고 항목 추출"""
        notices = []

        # 행 선택
        rows = await self.page.query_selector_all(self.SELECTORS["rows"])
        self.logger.debug(f"목록 행 수: {len(rows)}")

        for i, row in enumerate(rows):
            try:
                notice = await self._parse_row(row, i)
                if notice:
                    notices.append(notice)
            except Exception as e:
                self.logger.warning(f"행 {i} 파싱 실패: {e}")
                continue

        return notices

    async def _parse_row(self, row, index: int) -> Optional[BidNotice]:
        """단일 행 파싱"""
        cells = await row.query_selector_all("td")
        if len(cells) < 3:  # 최소 필드 수
            return None

        # 공고번호 추출
        bid_id = await self._extract_cell_text(cells, 1)  # 보통 두 번째 컬럼
        if not bid_id:
            bid_id = f"UNKNOWN_{index}"

        bid_id = self.extract_bid_id(bid_id) or bid_id

        # 제목 및 상세 URL 추출
        title, detail_url = await self._extract_title_and_url(cells)
        if not title:
            return None

        # 기관명
        organization = await self._extract_cell_text(cells, 3)

        # 입찰 유형
        bid_type_text = await self._extract_cell_text(cells, 4)
        bid_type = self._map_bid_type(bid_type_text)

        # 상태
        status_text = await self._extract_cell_text(cells, 5)
        status = self._map_status(status_text)

        # 마감일
        deadline_text = await self._extract_cell_text(cells, 6)
        deadline = self.parse_datetime(deadline_text)

        # 추정가격
        price_text = await self._extract_cell_text(cells, 7)
        estimated_price = self.parse_price(price_text)

        return BidNotice(
            bid_notice_id=bid_id,
            title=title,
            bid_type=bid_type,
            status=status,
            organization=organization,
            deadline=deadline,
            estimated_price=estimated_price,
            detail_url=detail_url,
            crawled_at=datetime.now(),
        )

    async def _extract_cell_text(self, cells: list, index: int) -> str:
        """셀 텍스트 추출 (인덱스 범위 체크)"""
        if index >= len(cells):
            return ""
        text = await cells[index].text_content()
        return self._clean_text(text) if text else ""

    async def _extract_title_and_url(self, cells: list) -> Tuple[str, Optional[str]]:
        """제목과 상세 URL 추출"""
        # 제목은 보통 세 번째 컬럼의 링크
        if len(cells) < 3:
            return "", None

        title_cell = cells[2]

        # 링크 찾기
        link = await title_cell.query_selector("a")
        if link:
            title = await link.text_content()
            href = await link.get_attribute("href")

            # onclick에서 URL 추출 시도
            if not href or href == "#":
                onclick = await link.get_attribute("onclick")
                if onclick:
                    href = self._extract_url_from_onclick(onclick)

            return self._clean_text(title) if title else "", href

        # 링크 없으면 셀 텍스트만
        text = await title_cell.text_content()
        return self._clean_text(text) if text else "", None

    def _extract_url_from_onclick(self, onclick: str) -> Optional[str]:
        """onclick 속성에서 URL 추출"""
        # 일반적인 패턴: fnDetail('param1', 'param2') 또는 location.href='url'
        patterns = [
            r"location\.href\s*=\s*['\"]([^'\"]+)['\"]",
            r"window\.open\s*\(['\"]([^'\"]+)['\"]",
            r"fnDetail\s*\(['\"]([^'\"]+)['\"]",
        ]

        for pattern in patterns:
            match = re.search(pattern, onclick)
            if match:
                return match.group(1)

        return None

    def _map_bid_type(self, text: str) -> BidType:
        """입찰 유형 매핑"""
        for keyword, bid_type in self.BID_TYPE_MAP.items():
            if keyword in text:
                return bid_type
        return BidType.OTHER

    def _map_status(self, text: str) -> BidStatus:
        """상태 매핑"""
        for keyword, status in self.STATUS_MAP.items():
            if keyword in text:
                return status
        return BidStatus.UNKNOWN

    async def _extract_pagination_info(self) -> Tuple[int, int, int]:
        """페이지네이션 정보 추출"""
        total_count = 0
        current_page = 1
        total_pages = 1

        # 전체 건수
        total_text = await self.get_text(self.SELECTORS["total_count"])
        if total_text:
            match = re.search(r"[\d,]+", total_text)
            if match:
                total_count = int(match.group().replace(",", ""))

        # 현재 페이지
        current_text = await self.get_text(self.SELECTORS["current_page"])
        if current_text:
            match = re.search(r"\d+", current_text)
            if match:
                current_page = int(match.group())

        # 전체 페이지 수 계산 또는 추출
        page_links = await self.page.query_selector_all(self.SELECTORS["page_links"])
        if page_links:
            last_page_nums = []
            for link in page_links:
                text = await link.text_content()
                if text:
                    match = re.search(r"\d+", text)
                    if match:
                        last_page_nums.append(int(match.group()))
            if last_page_nums:
                total_pages = max(last_page_nums)

        # 전체 건수로 페이지 수 계산 (페이지당 10건 가정)
        if total_count > 0 and total_pages == 1:
            total_pages = (total_count + 9) // 10

        return total_count, current_page, total_pages

    async def go_to_page(self, page_num: int) -> bool:
        """
        특정 페이지로 이동

        Args:
            page_num: 이동할 페이지 번호

        Returns:
            이동 성공 여부
        """
        try:
            # 페이지 링크 클릭
            page_link = await self.page.query_selector(
                f"{self.SELECTORS['page_links']}:has-text('{page_num}')"
            )

            if page_link:
                await page_link.click()
                await asyncio.sleep(1)  # 로딩 대기
                await self._wait_for_table()
                return True

            # 직접 URL 변경 시도
            current_url = self.page.url
            if "page=" in current_url:
                new_url = re.sub(r"page=\d+", f"page={page_num}", current_url)
            else:
                separator = "&" if "?" in current_url else "?"
                new_url = f"{current_url}{separator}page={page_num}"

            await self.page.goto(new_url)
            await self._wait_for_table()
            return True

        except Exception as e:
            self.logger.error(f"페이지 {page_num} 이동 실패: {e}")
            return False

    async def has_next_page(self) -> bool:
        """다음 페이지 존재 여부"""
        return await self.exists(self.SELECTORS["next_page"], timeout=2000)

    async def go_to_next_page(self) -> bool:
        """다음 페이지로 이동"""
        try:
            next_btn = await self.page.query_selector(self.SELECTORS["next_page"])
            if next_btn:
                await next_btn.click()
                await asyncio.sleep(1)
                await self._wait_for_table()
                return True
        except Exception as e:
            self.logger.error(f"다음 페이지 이동 실패: {e}")
        return False
