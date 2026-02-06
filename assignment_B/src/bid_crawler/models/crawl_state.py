"""
크롤링 상태 관리 모델

크롤링 진행 상태를 저장하여 중단된 지점부터 재시작할 수 있도록 합니다.
"""

from datetime import datetime
from typing import Optional, Set, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field, field_serializer


class CrawlProgress(BaseModel):
    """크롤링 진행 상태"""

    # 현재 위치
    current_page: int = Field(default=1, description="현재 페이지 번호")
    current_index: int = Field(default=0, description="현재 페이지 내 항목 인덱스")

    # 페이지 범위
    total_pages: Optional[int] = Field(default=None, description="전체 페이지 수")
    last_completed_page: int = Field(default=0, description="마지막 완료 페이지")

    # 필터/검색 상태
    keyword: Optional[str] = Field(default=None, description="검색 키워드")
    bid_type: Optional[str] = Field(default=None, description="입찰 유형 필터")


class CrawlStatistics(BaseModel):
    """크롤링 통계"""

    # 수집 건수
    total_collected: int = Field(default=0, description="전체 수집 건수")
    list_collected: int = Field(default=0, description="목록 수집 건수")
    detail_collected: int = Field(default=0, description="상세 수집 건수")

    # 오류 건수
    errors: int = Field(default=0, description="오류 발생 건수")
    retries: int = Field(default=0, description="재시도 횟수")
    skipped_duplicates: int = Field(default=0, description="중복 스킵 건수")

    # 성공률
    @property
    def success_rate(self) -> float:
        """성공률 계산"""
        total = self.total_collected + self.errors
        if total == 0:
            return 100.0
        return (self.total_collected / total) * 100


class CrawlState(BaseModel):
    """
    크롤링 전체 상태

    중단점 저장, 중복 방지, 통계 관리를 담당합니다.
    JSON 파일로 저장/로드되어 크롤러 재시작 시 복원됩니다.
    """

    # 실행 식별
    run_id: str = Field(..., description="실행 ID")
    started_at: datetime = Field(default_factory=datetime.now, description="시작 시간")
    last_updated_at: datetime = Field(default_factory=datetime.now, description="마지막 업데이트")

    # 상태
    is_running: bool = Field(default=False, description="실행 중 여부")
    is_completed: bool = Field(default=False, description="완료 여부")
    last_error: Optional[str] = Field(default=None, description="마지막 오류")

    # 진행 상황
    progress: CrawlProgress = Field(default_factory=CrawlProgress)
    statistics: CrawlStatistics = Field(default_factory=CrawlStatistics)

    # 중복 방지용 수집된 ID 목록
    collected_ids: Set[str] = Field(default_factory=set, description="수집된 공고 ID 목록")

    # 실패한 항목 (재시도 대상)
    failed_items: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="실패한 항목 목록 (재시도용)"
    )

    model_config = ConfigDict()

    @field_serializer('started_at', 'last_updated_at', when_used='json')
    @classmethod
    def serialize_datetime(cls, v: Optional[datetime]) -> Optional[str]:
        """datetime을 ISO 형식 문자열로 직렬화 (JSON 전용)"""
        return v.isoformat() if v else None

    @field_serializer('collected_ids', when_used='json')
    @classmethod
    def serialize_set(cls, v: Set[str]) -> List[str]:
        """set을 list로 직렬화 (JSON 전용)"""
        return list(v)

    def mark_collected(self, bid_id: str) -> bool:
        """
        ID를 수집 완료로 표시

        Args:
            bid_id: 입찰공고 ID

        Returns:
            True: 신규 수집, False: 이미 수집된 항목 (중복)
        """
        if bid_id in self.collected_ids:
            self.statistics.skipped_duplicates += 1
            return False

        self.collected_ids.add(bid_id)
        self.statistics.total_collected += 1
        self.last_updated_at = datetime.now()
        return True

    def is_collected(self, bid_id: str) -> bool:
        """이미 수집된 ID인지 확인"""
        return bid_id in self.collected_ids

    def record_error(self, error: str, item_info: Optional[Dict[str, Any]] = None) -> None:
        """오류 기록"""
        self.statistics.errors += 1
        self.last_error = error
        self.last_updated_at = datetime.now()

        if item_info:
            self.failed_items.append({
                "info": item_info,
                "error": error,
                "timestamp": datetime.now().isoformat(),
            })

    def record_retry(self) -> None:
        """재시도 기록"""
        self.statistics.retries += 1
        self.last_updated_at = datetime.now()

    def update_progress(
        self,
        page: Optional[int] = None,
        index: Optional[int] = None,
        total_pages: Optional[int] = None,
    ) -> None:
        """진행 상황 업데이트"""
        if page is not None:
            self.progress.current_page = page
        if index is not None:
            self.progress.current_index = index
        if total_pages is not None:
            self.progress.total_pages = total_pages
        self.last_updated_at = datetime.now()

    def complete_page(self, page: int) -> None:
        """페이지 완료 처리"""
        self.progress.last_completed_page = page
        self.progress.current_index = 0
        self.last_updated_at = datetime.now()

    def mark_completed(self) -> None:
        """크롤링 완료 처리"""
        self.is_completed = True
        self.is_running = False
        self.last_updated_at = datetime.now()

    def to_resumable_dict(self) -> Dict[str, Any]:
        """재시작용 딕셔너리 변환"""
        data = self.model_dump()
        data["collected_ids"] = list(self.collected_ids)
        return data

    @classmethod
    def from_resumable_dict(cls, data: Dict[str, Any]) -> "CrawlState":
        """딕셔너리에서 복원"""
        if "collected_ids" in data and isinstance(data["collected_ids"], list):
            data["collected_ids"] = set(data["collected_ids"])
        return cls(**data)
