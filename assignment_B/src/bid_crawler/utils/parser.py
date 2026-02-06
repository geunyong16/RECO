"""
파싱 유틸리티

텍스트 파싱, 데이터 변환 관련 유틸리티 함수를 제공합니다.
BaseScraper에서 분리된 순수 유틸리티로, 브라우저 없이 독립적으로 테스트 가능합니다.
"""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional


class ParserUtils:
    """
    파싱 유틸리티 클래스

    가격, 날짜, 입찰번호 등의 문자열 파싱을 담당합니다.
    모든 메서드는 정적 메서드로 구현되어 상태를 갖지 않습니다.

    Examples:
        >>> ParserUtils.parse_price("123,456,789원")
        Decimal('123456789')

        >>> ParserUtils.parse_datetime("2024-01-15 14:30")
        datetime.datetime(2024, 1, 15, 14, 30)
    """

    @staticmethod
    def clean_text(text: str) -> str:
        """
        텍스트 정리 (공백, 줄바꿈 정규화)

        연속된 공백/줄바꿈을 단일 공백으로 변환하고 앞뒤 공백을 제거합니다.

        Args:
            text: 원본 텍스트

        Returns:
            정리된 텍스트

        Examples:
            >>> ParserUtils.clean_text("  hello   world  ")
            'hello world'

            >>> ParserUtils.clean_text("line1\\n\\n  line2")
            'line1 line2'
        """
        if not text:
            return ""
        # 연속 공백/줄바꿈을 단일 공백으로
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def parse_price(text: str) -> Optional[Decimal]:
        """
        가격 문자열 파싱

        쉼표로 구분된 숫자 형식의 가격을 Decimal로 변환합니다.
        한글 단위(억, 만원 등)는 지원하지 않습니다.

        Args:
            text: 가격 문자열 (예: "123,456,789원", "1,000,000")

        Returns:
            파싱된 Decimal 값 또는 None (파싱 실패 시)

        Examples:
            >>> ParserUtils.parse_price("123,456,789원")
            Decimal('123456789')

            >>> ParserUtils.parse_price("약 1억 2천만원")
            None  # 한글 단위 미지원
        """
        if not text:
            return None

        # 숫자와 쉼표만 추출
        numbers = re.findall(r"[\d,]+", text)
        if not numbers:
            return None

        try:
            # 가장 긴 숫자열 사용 (가격일 가능성 높음)
            longest = max(numbers, key=len)
            # 쉼표 제거 후 Decimal 변환
            return Decimal(longest.replace(",", ""))
        except (ValueError, InvalidOperation):
            return None

    @staticmethod
    def parse_datetime(text: str) -> Optional[datetime]:
        """
        날짜/시간 문자열 파싱

        다양한 형식의 날짜/시간 문자열을 datetime 객체로 변환합니다.

        지원 형식:
            - "2024-01-15 14:30" (구분자: -, /, .)
            - "2024-01-15 14:30:00" (초 포함)
            - "2024/01/15" (날짜만)
            - "2024년 01월 15일 14시 30분" (한글 형식)
            - "2024년 01월 15일" (한글 날짜만)

        Args:
            text: 날짜/시간 문자열

        Returns:
            파싱된 datetime 또는 None (파싱 실패 시)

        Examples:
            >>> ParserUtils.parse_datetime("2024-01-15 14:30")
            datetime.datetime(2024, 1, 15, 14, 30)

            >>> ParserUtils.parse_datetime("2024년 01월 15일")
            datetime.datetime(2024, 1, 15, 0, 0)
        """
        if not text:
            return None

        text = ParserUtils.clean_text(text)

        # 패턴과 변환 함수 매핑
        patterns = [
            # 날짜 + 시간 (초 포함 가능)
            (
                r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?",
                lambda m: datetime(
                    int(m.group(1)), int(m.group(2)), int(m.group(3)),
                    int(m.group(4)), int(m.group(5)), int(m.group(6) or 0)
                )
            ),
            # 날짜만
            (
                r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})",
                lambda m: datetime(
                    int(m.group(1)), int(m.group(2)), int(m.group(3))
                )
            ),
            # 한글 형식 (시간 포함)
            (
                r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*(\d{1,2})시\s*(\d{2})분",
                lambda m: datetime(
                    int(m.group(1)), int(m.group(2)), int(m.group(3)),
                    int(m.group(4)), int(m.group(5))
                )
            ),
            # 한글 형식 (날짜만)
            (
                r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일",
                lambda m: datetime(
                    int(m.group(1)), int(m.group(2)), int(m.group(3))
                )
            ),
        ]

        for pattern, converter in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return converter(match)
                except (ValueError, IndexError):
                    continue

        return None

    @staticmethod
    def extract_bid_id(text: str) -> Optional[str]:
        """
        입찰공고번호 추출

        다양한 형식의 입찰공고번호를 추출합니다.

        지원 형식:
            - 날짜-순번 형식: "20240115-001"
            - 긴 숫자열: "2024011500001"
            - 문자+숫자 형식: "KEPCO-12345"

        Args:
            text: 원본 텍스트

        Returns:
            추출된 공고번호 또는 None (추출 실패 시)

        Examples:
            >>> ParserUtils.extract_bid_id("공고번호: 20240115-001")
            '20240115-001'
        """
        if not text:
            return None

        patterns = [
            r"(\d{8,}-\d+)",       # 날짜-순번 형식
            r"(\d{10,})",          # 긴 숫자열
            r"([A-Z0-9]{5,}-\d+)", # 문자+숫자 형식
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)

        # 패턴 매칭 실패 시 공백 제거한 텍스트 반환
        cleaned = re.sub(r"\s+", "", text)
        return cleaned if cleaned else None

    # 한글 숫자 단위 매핑
    KOREAN_UNITS = {
        "조": 1_000_000_000_000,
        "억": 100_000_000,
        "만": 10_000,
        "천": 1_000,
        "백": 100,
        "십": 10,
    }

    # 한글 숫자 매핑
    KOREAN_NUMBERS = {
        "일": 1, "이": 2, "삼": 3, "사": 4, "오": 5,
        "육": 6, "칠": 7, "팔": 8, "구": 9, "영": 0,
        "하나": 1, "둘": 2, "셋": 3, "넷": 4, "다섯": 5,
        "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9,
    }

    @staticmethod
    def parse_korean_price(text: str) -> Optional[Decimal]:
        """
        한글 단위가 포함된 가격 파싱

        "1억 2천만원", "5천만원", "약 3억원" 형식의 한글 가격을 파싱합니다.

        Args:
            text: 한글 가격 문자열

        Returns:
            파싱된 Decimal 값 또는 None

        Examples:
            >>> ParserUtils.parse_korean_price("1억 2천만원")
            Decimal('120000000')

            >>> ParserUtils.parse_korean_price("5천만원")
            Decimal('50000000')

            >>> ParserUtils.parse_korean_price("약 3억 5000만원")
            Decimal('350000000')
        """
        if not text:
            return None

        # 숫자만 있는 경우 먼저 시도
        result = ParserUtils.parse_price(text)
        if result:
            return result

        # 불필요한 문자 제거 (약, 원, 공백 등)
        cleaned = re.sub(r"[약원\s,]", "", text)

        if not cleaned:
            return None

        total = Decimal(0)
        current_number = Decimal(0)

        # 패턴: 숫자 + 단위 조합 추출
        # 예: "1억", "2천", "5000만" 등
        pattern = r"(\d+|[일이삼사오육칠팔구])([조억만천백십])"
        matches = list(re.finditer(pattern, cleaned))

        if not matches:
            return None

        for match in matches:
            num_str, unit = match.groups()

            # 숫자 변환 (아라비아 숫자 또는 한글 숫자)
            if num_str.isdigit():
                num = Decimal(num_str)
            elif num_str in ParserUtils.KOREAN_NUMBERS:
                num = Decimal(ParserUtils.KOREAN_NUMBERS[num_str])
            else:
                continue

            # 단위 적용
            if unit in ParserUtils.KOREAN_UNITS:
                unit_value = ParserUtils.KOREAN_UNITS[unit]
                total += num * unit_value

        return total if total > 0 else None

    @staticmethod
    def normalize_url(url: str, base_url: str) -> str:
        """
        URL 정규화

        상대 경로를 절대 경로로 변환합니다.

        Args:
            url: 상대 또는 절대 URL
            base_url: 기본 URL

        Returns:
            정규화된 절대 URL

        Examples:
            >>> ParserUtils.normalize_url("/detail?id=1", "https://example.com")
            'https://example.com/detail?id=1'
        """
        if not url:
            return ""

        if url.startswith(("http://", "https://")):
            return url

        base_url = base_url.rstrip("/")
        url = url if url.startswith("/") else f"/{url}"

        return f"{base_url}{url}"

    @staticmethod
    def extract_table_data(html_content: str) -> list:
        """
        HTML 테이블에서 데이터 추출 (단순 형태)

        Playwright 없이 HTML 문자열에서 테이블 데이터를 추출합니다.
        복잡한 테이블은 BaseScraper의 parse_table_to_dict 사용을 권장합니다.

        Args:
            html_content: HTML 문자열

        Returns:
            추출된 행 데이터 리스트

        Note:
            단순한 테이블 구조에만 적합합니다.
        """
        # 간단한 정규표현식 기반 추출
        rows = []
        row_pattern = r"<tr[^>]*>(.*?)</tr>"
        cell_pattern = r"<t[dh][^>]*>(.*?)</t[dh]>"

        for row_match in re.finditer(row_pattern, html_content, re.DOTALL | re.IGNORECASE):
            row_content = row_match.group(1)
            cells = []
            for cell_match in re.finditer(cell_pattern, row_content, re.DOTALL | re.IGNORECASE):
                cell_text = re.sub(r"<[^>]+>", "", cell_match.group(1))
                cells.append(ParserUtils.clean_text(cell_text))
            if cells:
                rows.append(cells)

        return rows
