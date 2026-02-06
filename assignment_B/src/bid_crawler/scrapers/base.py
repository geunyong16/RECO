"""
기본 스크래퍼 추상 클래스

모든 스크래퍼의 공통 인터페이스와 기능을 정의합니다.
Playwright 브라우저 상호작용에 집중하며, 파싱 로직은 ParserUtils에 위임합니다.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime
from decimal import Decimal

from playwright.async_api import Page

from bid_crawler.utils.logger import get_logger
from bid_crawler.utils.parser import ParserUtils
from bid_crawler.exceptions import ScraperException

logger = get_logger(__name__)


# 하위 호환성을 위해 ScraperError 별칭 유지
ScraperError = ScraperException


class BaseScraper(ABC):
    """
    스크래퍼 기본 클래스

    모든 스크래퍼가 상속받는 추상 클래스입니다.
    Playwright 페이지와의 상호작용에 집중하며,
    파싱 로직은 ParserUtils를 통해 위임합니다.

    Attributes:
        page: Playwright 페이지 인스턴스
        logger: 로거 인스턴스
        _parser: ParserUtils 인스턴스 (composition)
    """

    def __init__(self, page: Page):
        self.page = page
        self.logger = get_logger(self.__class__.__name__)
        self._parser = ParserUtils()  # Composition for parsing logic

    @abstractmethod
    async def scrape(self) -> Any:
        """
        스크래핑 실행

        Returns:
            스크래핑 결과 (하위 클래스에서 타입 정의)
        """
        pass

    # === Playwright 상호작용 메서드 ===

    async def get_text(
        self,
        selector: str,
        default: str = "",
        timeout: int = 5000,
    ) -> str:
        """
        선택자로 텍스트 추출

        Args:
            selector: CSS 선택자
            default: 요소가 없을 때 반환값
            timeout: 대기 시간 (ms)

        Returns:
            추출된 텍스트 또는 기본값
        """
        try:
            element = await self.page.wait_for_selector(selector, timeout=timeout)
            if element:
                text = await element.text_content()
                return self._clean_text(text) if text else default
        except Exception:
            pass
        return default

    async def get_all_texts(
        self,
        selector: str,
        timeout: int = 5000,
    ) -> List[str]:
        """
        선택자로 모든 텍스트 추출

        Args:
            selector: CSS 선택자
            timeout: 대기 시간 (ms)

        Returns:
            추출된 텍스트 리스트
        """
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            elements = await self.page.query_selector_all(selector)
            texts = []
            for el in elements:
                text = await el.text_content()
                if text:
                    texts.append(self._clean_text(text))
            return texts
        except Exception:
            return []

    async def get_attribute(
        self,
        selector: str,
        attribute: str,
        default: str = "",
        timeout: int = 5000,
    ) -> str:
        """
        선택자로 속성 값 추출

        Args:
            selector: CSS 선택자
            attribute: 속성명
            default: 요소가 없을 때 반환값
            timeout: 대기 시간 (ms)

        Returns:
            추출된 속성 값 또는 기본값
        """
        try:
            element = await self.page.wait_for_selector(selector, timeout=timeout)
            if element:
                value = await element.get_attribute(attribute)
                return value if value else default
        except Exception:
            pass
        return default

    async def get_inner_html(
        self,
        selector: str,
        default: str = "",
        timeout: int = 5000,
    ) -> str:
        """
        선택자로 내부 HTML 추출

        Args:
            selector: CSS 선택자
            default: 요소가 없을 때 반환값
            timeout: 대기 시간 (ms)

        Returns:
            추출된 HTML 또는 기본값
        """
        try:
            element = await self.page.wait_for_selector(selector, timeout=timeout)
            if element:
                html = await element.inner_html()
                return html if html else default
        except Exception:
            pass
        return default

    async def exists(self, selector: str, timeout: int = 3000) -> bool:
        """
        요소 존재 여부 확인

        Args:
            selector: CSS 선택자
            timeout: 대기 시간 (ms)

        Returns:
            요소가 존재하면 True
        """
        try:
            element = await self.page.wait_for_selector(selector, timeout=timeout)
            return element is not None
        except Exception:
            return False

    async def count_elements(self, selector: str) -> int:
        """
        요소 개수 확인

        Args:
            selector: CSS 선택자

        Returns:
            요소 개수
        """
        elements = await self.page.query_selector_all(selector)
        return len(elements)

    async def click(self, selector: str, timeout: int = 5000) -> bool:
        """
        요소 클릭

        Args:
            selector: CSS 선택자
            timeout: 대기 시간 (ms)

        Returns:
            클릭 성공 여부
        """
        try:
            element = await self.page.wait_for_selector(selector, timeout=timeout)
            if element:
                await element.click()
                return True
        except Exception as e:
            self.logger.warning(f"Click failed on {selector}: {e}")
        return False

    async def navigate(self, url: str, wait_until: str = "networkidle") -> None:
        """
        URL로 이동

        Args:
            url: 이동할 URL
            wait_until: 대기 조건 (networkidle, load, domcontentloaded)

        Raises:
            ScraperException: 네비게이션 실패 시
        """
        try:
            await self.page.goto(url, wait_until=wait_until)
        except Exception as e:
            raise ScraperException(f"Navigation failed: {e}", url=url)

    # === 파싱 유틸리티 (ParserUtils로 위임) ===
    # 하위 호환성을 위해 기존 메서드 시그니처 유지

    def _clean_text(self, text: str) -> str:
        """
        텍스트 정리 (공백, 줄바꿈 정규화)

        ParserUtils로 위임합니다.

        Args:
            text: 원본 텍스트

        Returns:
            정리된 텍스트
        """
        return ParserUtils.clean_text(text)

    def parse_price(self, text: str) -> Optional[Decimal]:
        """
        가격 문자열 파싱

        ParserUtils로 위임합니다.
        반환 타입이 int에서 Decimal로 변경되었습니다.

        Args:
            text: 가격 문자열 (예: "123,456,789원")

        Returns:
            파싱된 Decimal 값 또는 None

        Note:
            하위 호환성: 기존 int 반환 코드는 Decimal로 변경됨
        """
        return ParserUtils.parse_price(text)

    def parse_datetime(self, text: str) -> Optional[datetime]:
        """
        날짜/시간 문자열 파싱

        ParserUtils로 위임합니다.

        Args:
            text: 날짜/시간 문자열

        Returns:
            파싱된 datetime 또는 None
        """
        return ParserUtils.parse_datetime(text)

    def extract_bid_id(self, text: str) -> Optional[str]:
        """
        입찰공고번호 추출

        ParserUtils로 위임합니다.

        Args:
            text: 원본 텍스트

        Returns:
            추출된 공고번호 또는 None
        """
        return ParserUtils.extract_bid_id(text)

    # === 테이블 파싱 유틸리티 (Playwright + Parser 조합) ===

    async def parse_table_to_dict(
        self,
        table_selector: str,
        header_selector: str = "th",
        data_selector: str = "td",
    ) -> List[Dict[str, str]]:
        """
        HTML 테이블을 딕셔너리 리스트로 변환

        Playwright를 통해 테이블 요소를 추출하고,
        ParserUtils를 통해 텍스트를 정리합니다.

        Args:
            table_selector: 테이블 CSS 선택자
            header_selector: 헤더 셀 선택자
            data_selector: 데이터 셀 선택자

        Returns:
            [{헤더1: 값1, 헤더2: 값2, ...}, ...]
        """
        try:
            await self.page.wait_for_selector(table_selector, timeout=5000)
        except Exception:
            return []

        rows = await self.page.query_selector_all(f"{table_selector} tr")
        if not rows:
            return []

        # 헤더 추출
        headers = []
        first_row = rows[0]
        header_cells = await first_row.query_selector_all(header_selector)

        if header_cells:
            for cell in header_cells:
                text = await cell.text_content()
                headers.append(self._clean_text(text) if text else "")
        else:
            # th가 없으면 첫 번째 행의 td를 헤더로 사용
            data_cells = await first_row.query_selector_all(data_selector)
            for cell in data_cells:
                text = await cell.text_content()
                headers.append(self._clean_text(text) if text else "")
            rows = rows[1:]  # 첫 행 제외

        # 데이터 행 파싱
        result = []
        for row in rows[1:] if header_cells else rows:
            cells = await row.query_selector_all(data_selector)
            if not cells:
                continue

            row_data = {}
            for i, cell in enumerate(cells):
                if i < len(headers):
                    text = await cell.text_content()
                    row_data[headers[i]] = self._clean_text(text) if text else ""

            if row_data:
                result.append(row_data)

        return result

    async def parse_definition_list(
        self,
        container_selector: str,
        term_selector: str = "dt",
        desc_selector: str = "dd",
    ) -> Dict[str, str]:
        """
        정의 목록(dl/dt/dd)을 딕셔너리로 변환

        Args:
            container_selector: 컨테이너 CSS 선택자
            term_selector: 용어 선택자
            desc_selector: 설명 선택자

        Returns:
            {용어1: 설명1, 용어2: 설명2, ...}
        """
        result = {}

        try:
            await self.page.wait_for_selector(container_selector, timeout=5000)
        except Exception:
            return result

        terms = await self.page.query_selector_all(f"{container_selector} {term_selector}")
        descs = await self.page.query_selector_all(f"{container_selector} {desc_selector}")

        for term, desc in zip(terms, descs):
            term_text = await term.text_content()
            desc_text = await desc.text_content()

            if term_text:
                key = self._clean_text(term_text)
                value = self._clean_text(desc_text) if desc_text else ""
                result[key] = value

        return result
