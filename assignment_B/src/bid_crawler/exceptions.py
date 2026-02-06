"""
도메인 예외 정의

비즈니스 로직에서 발생하는 예외를 정의합니다.
Enterprise-Grade Backend Architecture의 일관된 예외 처리를 위한 계층화된 예외 클래스입니다.
"""

from typing import Optional, Any


class BidCrawlerException(Exception):
    """
    기본 예외 클래스

    모든 bid_crawler 예외의 기본 클래스입니다.
    상세 정보를 담을 수 있는 details 딕셔너리를 제공합니다.
    """

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (details: {self.details})"
        return self.message


class InvalidBidDataException(BidCrawlerException):
    """
    유효하지 않은 입찰 데이터 예외

    필수 필드 누락, 데이터 형식 오류, 유효하지 않은 값 등에서 발생합니다.

    Attributes:
        field_name: 오류가 발생한 필드명
        invalid_value: 유효하지 않은 값

    Examples:
        >>> raise InvalidBidDataException(
        ...     "Invalid price format",
        ...     field_name="estimated_price",
        ...     invalid_value="invalid"
        ... )
    """

    def __init__(
        self,
        message: str,
        field_name: Optional[str] = None,
        invalid_value: Any = None,
    ):
        details = {}
        if field_name:
            details["field_name"] = field_name
        if invalid_value is not None:
            details["invalid_value"] = str(invalid_value)

        super().__init__(message, details)
        self.field_name = field_name
        self.invalid_value = invalid_value


class DuplicateBidException(BidCrawlerException):
    """
    중복 입찰 공고 예외

    이미 수집된 공고를 다시 저장하려 할 때 발생합니다.

    Attributes:
        bid_id: 중복된 입찰공고 ID

    Examples:
        >>> raise DuplicateBidException("20240115-001")
    """

    def __init__(self, bid_id: str):
        super().__init__(
            f"Duplicate bid notice: {bid_id}",
            {"bid_id": bid_id}
        )
        self.bid_id = bid_id


class ScraperException(BidCrawlerException):
    """
    스크래핑 오류

    웹 페이지 스크래핑 중 발생하는 오류입니다.
    선택자 오류, 페이지 로드 실패, 타임아웃 등이 해당됩니다.

    Attributes:
        selector: 오류가 발생한 CSS 선택자
        url: 오류가 발생한 URL

    Examples:
        >>> raise ScraperException(
        ...     "Element not found",
        ...     selector=".bid-list",
        ...     url="https://example.com/bids"
        ... )
    """

    def __init__(
        self,
        message: str,
        selector: Optional[str] = None,
        url: Optional[str] = None,
    ):
        details = {}
        if selector:
            details["selector"] = selector
        if url:
            details["url"] = url

        super().__init__(message, details)
        self.selector = selector
        self.url = url


class RepositoryException(BidCrawlerException):
    """
    저장소 오류

    데이터 저장/조회 중 발생하는 오류입니다.
    파일 I/O 오류, 직렬화 오류 등이 해당됩니다.

    Examples:
        >>> raise RepositoryException("Failed to save bid data: disk full")
    """
    pass


class ConfigurationException(BidCrawlerException):
    """
    설정 오류

    잘못된 설정 값이나 필수 설정 누락 시 발생합니다.

    Examples:
        >>> raise ConfigurationException("Missing required config: base_url")
    """
    pass


class NavigationException(ScraperException):
    """
    페이지 네비게이션 오류

    페이지 이동, 다음 페이지 탐색 등에서 발생하는 오류입니다.

    Examples:
        >>> raise NavigationException(
        ...     "Failed to navigate to next page",
        ...     url="https://example.com/bids?page=2"
        ... )
    """
    pass


class ParsingException(BidCrawlerException):
    """
    파싱 오류

    텍스트 파싱 중 발생하는 오류입니다.
    가격, 날짜 등의 형식 파싱 실패가 해당됩니다.

    Attributes:
        raw_value: 파싱 시도한 원본 값
        expected_format: 기대한 형식

    Examples:
        >>> raise ParsingException(
        ...     "Failed to parse price",
        ...     raw_value="약 1억원",
        ...     expected_format="숫자,숫자 형식"
        ... )
    """

    def __init__(
        self,
        message: str,
        raw_value: Optional[str] = None,
        expected_format: Optional[str] = None,
    ):
        details = {}
        if raw_value:
            details["raw_value"] = raw_value
        if expected_format:
            details["expected_format"] = expected_format

        super().__init__(message, details)
        self.raw_value = raw_value
        self.expected_format = expected_format
