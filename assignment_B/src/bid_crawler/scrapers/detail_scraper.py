"""
상세 페이지 스크래퍼

입찰공고 상세 페이지에서 모든 정보를 추출합니다.
"""

import asyncio
import re
from typing import List, Optional, Dict, Any
from datetime import datetime

from playwright.async_api import Page

from bid_crawler.scrapers.base import BaseScraper, ScraperError
from bid_crawler.models.bid_notice import BidNotice, BidNoticeDetail, BidType, BidStatus
from bid_crawler.utils.logger import get_logger

logger = get_logger(__name__)


class DetailScraper(BaseScraper):
    """
    입찰공고 상세 스크래퍼

    상세 페이지를 파싱하여 BidNoticeDetail 객체를 반환합니다.
    """

    # 상세 페이지 선택자 (실제 사이트에 맞게 조정 필요)
    SELECTORS = {
        # 컨테이너
        "detail_container": ".detail_view, .view_table, #detailView",
        "info_table": "table.info_table, table.view_tb, .detail_info table",

        # 기본 정보
        "bid_id": "th:has-text('공고번호') + td, .bid_no",
        "title": "th:has-text('공고명') + td, .title, h3.tit",
        "bid_type": "th:has-text('입찰유형') + td, th:has-text('업종') + td",
        "status": "th:has-text('상태') + td, th:has-text('진행상태') + td",

        # 기관 정보
        "organization": "th:has-text('공고기관') + td, th:has-text('발주기관') + td",
        "demand_org": "th:has-text('수요기관') + td",

        # 일시 정보
        "announce_date": "th:has-text('공고일') + td, th:has-text('공고일시') + td",
        "deadline": "th:has-text('마감') + td, th:has-text('입찰마감') + td",

        # 금액 정보
        "estimated_price": "th:has-text('추정가') + td, th:has-text('예정가격') + td",
        "base_price": "th:has-text('기초금액') + td",

        # 상세 정보
        "bid_method": "th:has-text('입찰방식') + td, th:has-text('낙찰방법') + td",
        "contract_method": "th:has-text('계약방법') + td",
        "qualification": "th:has-text('참가자격') + td, th:has-text('입찰참가자격') + td",

        # 지역 정보
        "region": "th:has-text('지역') + td, th:has-text('납품지역') + td",
        "delivery_location": "th:has-text('납품장소') + td, th:has-text('납품지') + td",

        # 담당자 정보
        "contact_dept": "th:has-text('담당부서') + td",
        "contact_person": "th:has-text('담당자') + td",
        "contact_phone": "th:has-text('전화') + td, th:has-text('연락처') + td",
        "contact_email": "th:has-text('이메일') + td, th:has-text('메일') + td",

        # 첨부파일
        "attachments": ".attach_list a, .file_list a, a[href*='download']",

        # 참조번호
        "reference_no": "th:has-text('참조번호') + td, th:has-text('사업번호') + td",
        "registration_no": "th:has-text('사업자등록') + td",
    }

    # 필드명-선택자 매핑 (자동 추출용)
    FIELD_SELECTORS = {
        "bid_notice_id": "bid_id",
        "title": "title",
        "organization": "organization",
        "demand_organization": "demand_org",
        "bid_method": "bid_method",
        "contract_method": "contract_method",
        "qualification": "qualification",
        "region": "region",
        "delivery_location": "delivery_location",
        "contact_department": "contact_dept",
        "contact_person": "contact_person",
        "contact_phone": "contact_phone",
        "contact_email": "contact_email",
        "reference_no": "reference_no",
        "registration_no": "registration_no",
    }

    async def scrape(self, base_notice: Optional[BidNotice] = None) -> BidNoticeDetail:
        """
        상세 페이지 스크래핑

        Args:
            base_notice: 목록에서 추출한 기본 정보 (있으면 병합)

        Returns:
            BidNoticeDetail: 상세 정보 객체
        """
        # 상세 컨테이너 로드 대기
        await self._wait_for_detail()

        # 모든 정보 테이블에서 데이터 추출
        raw_data = await self._extract_all_info()

        # 구조화된 객체 생성
        detail = self._build_detail(raw_data, base_notice)

        # 첨부파일 추출
        detail.attachments = await self._extract_attachments()

        # 원본 HTML 저장 (디버깅용, 선택적)
        # detail.raw_html = await self.page.content()

        detail.detail_crawled_at = datetime.now()
        detail.crawl_success = True

        return detail

    async def _wait_for_detail(self, timeout: int = 10000) -> None:
        """상세 페이지 로드 대기"""
        selectors = self.SELECTORS["detail_container"].split(", ")

        for selector in selectors:
            try:
                await self.page.wait_for_selector(selector, timeout=timeout // len(selectors))
                self.logger.debug(f"상세 컨테이너 로드됨: {selector}")
                return
            except Exception:
                continue

        # 테이블이라도 있으면 진행
        if await self.exists("table", timeout=3000):
            self.logger.debug("기본 테이블 로드됨")
            return

        raise ScraperError("상세 페이지를 찾을 수 없습니다")

    async def _extract_all_info(self) -> Dict[str, str]:
        """모든 정보 테이블에서 데이터 추출"""
        data = {}

        # 정보 테이블 파싱 시도
        tables = await self.page.query_selector_all("table")

        for table in tables:
            rows = await table.query_selector_all("tr")
            for row in rows:
                th = await row.query_selector("th")
                td = await row.query_selector("td")

                if th and td:
                    key_text = await th.text_content()
                    value_text = await td.text_content()

                    if key_text:
                        key = self._clean_text(key_text)
                        value = self._clean_text(value_text) if value_text else ""
                        data[key] = value

        # 개별 선택자로 추가 추출
        for field_name, selector_key in self.FIELD_SELECTORS.items():
            if field_name not in data or not data.get(field_name):
                selector = self.SELECTORS.get(selector_key, "")
                if selector:
                    value = await self.get_text(selector)
                    if value:
                        data[field_name] = value

        return data

    def _build_detail(
        self,
        raw_data: Dict[str, str],
        base_notice: Optional[BidNotice] = None,
    ) -> BidNoticeDetail:
        """원시 데이터에서 BidNoticeDetail 객체 생성"""

        # 기본값 설정
        if base_notice:
            detail_data = base_notice.model_dump()
        else:
            detail_data = {
                "bid_notice_id": "UNKNOWN",
                "title": "제목 없음",
            }

        # 매핑 테이블
        field_mapping = {
            # 한글 키 -> 필드명
            "공고번호": "bid_notice_id",
            "공고명": "title",
            "공고기관": "organization",
            "수요기관": "demand_organization",
            "공고일": "announce_date",
            "공고일시": "announce_date",
            "입찰마감일시": "deadline",
            "마감일시": "deadline",
            "추정가격": "estimated_price",
            "예정가격": "estimated_price",
            "기초금액": "base_price",
            "입찰방식": "bid_method",
            "낙찰방법": "bid_method",
            "계약방법": "contract_method",
            "참가자격": "qualification",
            "입찰참가자격": "qualification",
            "지역": "region",
            "납품지역": "region",
            "납품장소": "delivery_location",
            "담당부서": "contact_department",
            "담당자": "contact_person",
            "전화번호": "contact_phone",
            "연락처": "contact_phone",
            "이메일": "contact_email",
            "참조번호": "reference_no",
            "사업자등록번호": "registration_no",
        }

        # 원시 데이터 매핑
        for raw_key, value in raw_data.items():
            field_name = field_mapping.get(raw_key)
            if field_name and value:
                # 타입 변환
                if field_name in ["announce_date", "deadline"]:
                    parsed = self.parse_datetime(value)
                    if parsed:
                        detail_data[field_name] = parsed
                elif field_name in ["estimated_price", "base_price"]:
                    parsed = self.parse_price(value)
                    if parsed:
                        detail_data[field_name] = parsed
                else:
                    detail_data[field_name] = value

        # 입찰 유형 매핑
        bid_type_text = raw_data.get("입찰유형", "") or raw_data.get("업종", "")
        if bid_type_text:
            detail_data["bid_type"] = self._map_bid_type(bid_type_text)

        # 상태 매핑
        status_text = raw_data.get("상태", "") or raw_data.get("진행상태", "")
        if status_text:
            detail_data["status"] = self._map_status(status_text)

        return BidNoticeDetail(**detail_data)

    def _map_bid_type(self, text: str) -> BidType:
        """입찰 유형 매핑"""
        mapping = {
            "물품": BidType.GOODS,
            "용역": BidType.SERVICE,
            "공사": BidType.CONSTRUCTION,
            "외자": BidType.FOREIGN,
        }
        for keyword, bid_type in mapping.items():
            if keyword in text:
                return bid_type
        return BidType.OTHER

    def _map_status(self, text: str) -> BidStatus:
        """상태 매핑"""
        mapping = {
            "공고중": BidStatus.OPEN,
            "진행중": BidStatus.OPEN,
            "마감": BidStatus.CLOSED,
            "취소": BidStatus.CANCELLED,
            "연기": BidStatus.POSTPONED,
            "재공고": BidStatus.REBID,
        }
        for keyword, status in mapping.items():
            if keyword in text:
                return status
        return BidStatus.UNKNOWN

    async def _extract_attachments(self) -> List[str]:
        """첨부파일 목록 추출"""
        attachments = []

        selectors = self.SELECTORS["attachments"].split(", ")
        for selector in selectors:
            links = await self.page.query_selector_all(selector)
            for link in links:
                text = await link.text_content()
                href = await link.get_attribute("href")

                if text:
                    filename = self._clean_text(text)
                    if href:
                        attachments.append(f"{filename} ({href})")
                    else:
                        attachments.append(filename)

        return attachments

    async def scrape_from_url(
        self,
        url: str,
        base_notice: Optional[BidNotice] = None,
    ) -> BidNoticeDetail:
        """
        URL에서 상세 정보 스크래핑

        Args:
            url: 상세 페이지 URL
            base_notice: 기본 정보

        Returns:
            BidNoticeDetail: 상세 정보 객체
        """
        try:
            await self.page.goto(url, wait_until="networkidle")
            await asyncio.sleep(1)  # 동적 로딩 대기
            return await self.scrape(base_notice)
        except Exception as e:
            self.logger.error(f"상세 페이지 로드 실패 ({url}): {e}")

            # 실패 시 기본 정보만 반환
            if base_notice:
                return BidNoticeDetail(
                    **base_notice.model_dump(),
                    crawl_success=False,
                    crawl_error=str(e),
                    detail_crawled_at=datetime.now(),
                )

            raise ScraperError(f"상세 페이지 스크래핑 실패: {e}")
