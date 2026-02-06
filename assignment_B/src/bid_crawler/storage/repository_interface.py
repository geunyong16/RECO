"""
저장소 인터페이스 정의

Repository 패턴의 추상화 계층입니다.
DIP(Dependency Inversion Principle)를 적용하여
상위 레벨 모듈이 하위 레벨 모듈에 직접 의존하지 않도록 합니다.
"""

from abc import abstractmethod
from typing import Protocol, Optional, List, TypeVar, runtime_checkable
from datetime import datetime

from bid_crawler.models.bid_notice import BidNotice, BidNoticeDetail


T = TypeVar('T', bound=BidNotice)


@runtime_checkable
class BidRepository(Protocol[T]):
    """
    입찰공고 저장소 인터페이스

    모든 저장소 구현체가 따라야 하는 프로토콜입니다.
    Protocol을 사용하여 구조적 서브타이핑(structural subtyping)을 지원합니다.

    Attributes:
        T: BidNotice 또는 그 하위 클래스

    Examples:
        >>> class JsonStorage(BidRepository[BidNoticeDetail]):
        ...     def save(self, bid: BidNoticeDetail) -> bool:
        ...         # 구현
        ...         pass
    """

    @abstractmethod
    def save(self, bid: T) -> bool:
        """
        입찰공고 저장

        Args:
            bid: 저장할 입찰공고

        Returns:
            저장 성공 여부

        Raises:
            DuplicateBidException: 이미 존재하는 ID이고 raise_on_duplicate=True인 경우
            RepositoryException: 저장 실패 시
        """
        ...

    @abstractmethod
    def save_batch(self, bids: List[T]) -> int:
        """
        다중 입찰공고 배치 저장

        여러 입찰공고를 한 번에 저장합니다.
        중복된 항목은 건너뜁니다.

        Args:
            bids: 저장할 입찰공고 리스트

        Returns:
            실제로 저장된 건수
        """
        ...

    @abstractmethod
    def exists(self, bid_id: str) -> bool:
        """
        ID 존재 여부 확인

        Args:
            bid_id: 입찰공고 ID

        Returns:
            존재하면 True
        """
        ...

    @abstractmethod
    def find_by_id(self, bid_id: str) -> Optional[T]:
        """
        ID로 입찰공고 조회

        Args:
            bid_id: 입찰공고 ID

        Returns:
            조회된 입찰공고 또는 None (없는 경우)
        """
        ...

    @abstractmethod
    def find_all(self, limit: Optional[int] = None) -> List[T]:
        """
        모든 입찰공고 조회

        Args:
            limit: 최대 조회 건수 (None이면 전체)

        Returns:
            입찰공고 리스트
        """
        ...

    @abstractmethod
    def count(self) -> int:
        """
        저장된 총 건수

        Returns:
            저장된 입찰공고 수
        """
        ...

    @abstractmethod
    def flush(self) -> bool:
        """
        버퍼 플러시

        버퍼에 있는 데이터를 영구 저장소에 기록합니다.
        버퍼를 사용하지 않는 구현체에서는 True만 반환합니다.

        Returns:
            플러시 성공 여부
        """
        ...

    @abstractmethod
    def close(self) -> None:
        """
        저장소 연결 종료

        리소스를 정리하고 연결을 종료합니다.
        flush()를 내부적으로 호출해야 합니다.
        """
        ...


@runtime_checkable
class BidRepositoryWithQuery(BidRepository[T], Protocol):
    """
    쿼리 기능이 추가된 저장소 인터페이스

    기본 CRUD 외에 고급 조회 기능이 필요한 저장소용 확장 인터페이스입니다.
    데이터베이스 기반 저장소에서 구현합니다.

    Examples:
        >>> class PostgresStorage(BidRepositoryWithQuery[BidNoticeDetail]):
        ...     def find_by_status(self, status: str) -> List[BidNoticeDetail]:
        ...         # SQL 쿼리 구현
        ...         pass
    """

    @abstractmethod
    def find_by_status(self, status: str) -> List[T]:
        """
        상태별 조회

        Args:
            status: 입찰 상태 (예: "공고중", "마감")

        Returns:
            해당 상태의 입찰공고 리스트
        """
        ...

    @abstractmethod
    def find_by_date_range(
        self,
        start: datetime,
        end: datetime,
    ) -> List[T]:
        """
        날짜 범위 조회

        Args:
            start: 시작 일시
            end: 종료 일시

        Returns:
            해당 기간의 입찰공고 리스트
        """
        ...

    @abstractmethod
    def find_valuable(self, threshold: int) -> List[T]:
        """
        가치있는 입찰 조회

        추정가격이 기준 이상인 입찰공고를 조회합니다.

        Args:
            threshold: 기준 금액 (원)

        Returns:
            기준 이상의 입찰공고 리스트
        """
        ...

    @abstractmethod
    def find_by_organization(self, organization: str) -> List[T]:
        """
        기관별 조회

        Args:
            organization: 기관명 (부분 일치)

        Returns:
            해당 기관의 입찰공고 리스트
        """
        ...


class InMemoryRepository(BidRepository[T]):
    """
    메모리 기반 저장소 구현

    테스트용 인메모리 저장소입니다.
    실제 파일 I/O 없이 메모리에만 저장합니다.

    Examples:
        >>> repo = InMemoryRepository[BidNoticeDetail]()
        >>> repo.save(bid)
        True
        >>> repo.find_by_id("12345")
        BidNoticeDetail(...)
    """

    def __init__(self):
        self._storage: dict[str, T] = {}

    def save(self, bid: T) -> bool:
        """저장"""
        if bid.bid_notice_id in self._storage:
            return False
        self._storage[bid.bid_notice_id] = bid
        return True

    def save_batch(self, bids: List[T]) -> int:
        """배치 저장"""
        count = 0
        for bid in bids:
            if self.save(bid):
                count += 1
        return count

    def exists(self, bid_id: str) -> bool:
        """존재 확인"""
        return bid_id in self._storage

    def find_by_id(self, bid_id: str) -> Optional[T]:
        """ID로 조회"""
        return self._storage.get(bid_id)

    def find_all(self, limit: Optional[int] = None) -> List[T]:
        """전체 조회"""
        items = list(self._storage.values())
        if limit:
            return items[:limit]
        return items

    def count(self) -> int:
        """건수"""
        return len(self._storage)

    def flush(self) -> bool:
        """플러시 (no-op)"""
        return True

    def close(self) -> None:
        """종료"""
        self._storage.clear()
