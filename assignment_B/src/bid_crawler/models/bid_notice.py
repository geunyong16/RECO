"""
입찰공고 데이터 모델

나라장터 입찰공고의 목록 및 상세 정보를 구조화합니다.
Domain-Driven Design 원칙에 따라 도메인 행동을 포함합니다.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Any
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, field_validator, field_serializer

from bid_crawler.exceptions import InvalidBidDataException


class BidType(str, Enum):
    """입찰 유형"""
    GOODS = "물품"          # 물품 구매
    SERVICE = "용역"        # 용역 계약
    CONSTRUCTION = "공사"   # 시설 공사
    FOREIGN = "외자"        # 외자 구매
    OTHER = "기타"          # 기타


class BidStatus(str, Enum):
    """입찰 상태"""
    OPEN = "공고중"
    CLOSED = "마감"
    CANCELLED = "취소"
    POSTPONED = "연기"
    REBID = "재공고"
    UNKNOWN = "알수없음"


class BidNotice(BaseModel):
    """
    입찰공고 목록 항목 모델

    목록 페이지에서 추출 가능한 기본 정보를 담습니다.
    도메인 행동(is_valuable, is_open, can_participate 등)을 포함합니다.
    """

    # 필수 식별 정보
    bid_notice_id: str = Field(..., description="입찰공고번호 (고유 식별자)")
    title: str = Field(..., description="공고명")

    # 기본 정보
    bid_type: BidType = Field(default=BidType.OTHER, description="입찰 유형")
    status: BidStatus = Field(default=BidStatus.UNKNOWN, description="공고 상태")

    # 기관 정보
    organization: Optional[str] = Field(default=None, description="공고기관명")
    demand_organization: Optional[str] = Field(default=None, description="수요기관명")

    # 일시 정보
    announce_date: Optional[datetime] = Field(default=None, description="공고일시")
    deadline: Optional[datetime] = Field(default=None, description="입찰마감일시")

    # 금액 정보 - int에서 Decimal로 변경 (정밀도 보장)
    estimated_price: Optional[Decimal] = Field(default=None, description="추정가격 (원)")
    base_price: Optional[Decimal] = Field(default=None, description="기초금액 (원)")

    # 메타 정보
    detail_url: Optional[str] = Field(default=None, description="상세 페이지 URL")
    crawled_at: datetime = Field(default_factory=datetime.now, description="수집 일시")

    # === Validators ===

    @field_validator('estimated_price', 'base_price', mode='before')
    @classmethod
    def convert_to_decimal(cls, v):
        """
        int/float/str을 Decimal로 변환

        다양한 입력 타입을 안전하게 Decimal로 변환합니다.
        무효한 값은 InvalidBidDataException을 발생시킵니다.
        """
        if v is None:
            return None
        if isinstance(v, Decimal):
            return v
        try:
            # int, float, str 모두 문자열로 변환 후 Decimal 생성
            return Decimal(str(v))
        except Exception:
            raise InvalidBidDataException(
                f"Invalid price value: {v}",
                field_name="price",
                invalid_value=v,
            )

    # === Domain Behaviors ===

    def is_valuable(self, threshold: Decimal = Decimal("100000000")) -> bool:
        """
        가치 있는 입찰 여부 판단

        추정가격이 기준 금액 이상인지 확인합니다.

        Args:
            threshold: 기준 금액 (기본 1억원 = 100,000,000)

        Returns:
            추정가격이 기준 이상이면 True, 아니면 False

        Examples:
            >>> bid = BidNotice(bid_notice_id="1", title="Test", estimated_price=500000000)
            >>> bid.is_valuable()  # 5억원
            True
        """
        if self.estimated_price is None:
            return False
        return self.estimated_price >= threshold

    def is_open(self) -> bool:
        """
        공고중 상태인지 확인

        Returns:
            공고중이면 True
        """
        return self.status == BidStatus.OPEN

    def is_expired(self) -> bool:
        """
        마감일이 지났는지 확인

        Returns:
            마감일이 지났으면 True, 마감일이 없으면 False
        """
        if self.deadline is None:
            return False
        return datetime.now() > self.deadline

    def can_participate(self) -> bool:
        """
        참가 가능 여부 판단

        공고중이고 마감일이 지나지 않았으면 참가 가능합니다.

        Returns:
            참가 가능하면 True
        """
        return self.is_open() and not self.is_expired()

    def transition_to(self, new_status: BidStatus) -> "BidNotice":
        """
        상태 전환 (불변성 유지)

        유효한 상태 전환만 허용합니다.
        - OPEN -> CLOSED, CANCELLED, POSTPONED
        - POSTPONED -> OPEN, CANCELLED, REBID
        - REBID -> OPEN

        Args:
            new_status: 새 상태

        Returns:
            새 상태가 적용된 새 BidNotice 인스턴스 (원본은 변경되지 않음)

        Raises:
            InvalidBidDataException: 허용되지 않는 상태 전환인 경우
        """
        valid_transitions = {
            BidStatus.OPEN: [BidStatus.CLOSED, BidStatus.CANCELLED, BidStatus.POSTPONED],
            BidStatus.POSTPONED: [BidStatus.OPEN, BidStatus.CANCELLED, BidStatus.REBID],
            BidStatus.REBID: [BidStatus.OPEN],
        }

        allowed = valid_transitions.get(self.status, [])
        if new_status not in allowed:
            raise InvalidBidDataException(
                f"Invalid status transition: {self.status.value} -> {new_status.value}",
                field_name="status",
                invalid_value=new_status.value,
            )

        return self.model_copy(update={"status": new_status})

    def get_price_display(self) -> str:
        """
        가격 표시 문자열 생성

        추정가격을 읽기 쉬운 형식으로 포맷합니다.

        Returns:
            포맷된 가격 문자열 (예: "1억 2,000만원")
        """
        if self.estimated_price is None:
            return "미정"

        price = int(self.estimated_price)
        if price >= 100000000:  # 1억 이상
            eok = price // 100000000
            man = (price % 100000000) // 10000
            if man > 0:
                return f"{eok}억 {man:,}만원"
            return f"{eok}억원"
        elif price >= 10000:  # 1만원 이상
            return f"{price // 10000:,}만원"
        else:
            return f"{price:,}원"

    model_config = ConfigDict(
        ser_json_timedelta="iso8601",
    )

    @field_serializer('crawled_at', 'announce_date', 'deadline', when_used='json')
    @classmethod
    def serialize_datetime(cls, v: Optional[datetime]) -> Optional[str]:
        """datetime을 ISO 형식 문자열로 직렬화 (JSON 전용)"""
        return v.isoformat() if v else None

    @field_serializer('estimated_price', 'base_price', when_used='json')
    @classmethod
    def serialize_decimal(cls, v: Optional[Decimal]) -> Optional[str]:
        """Decimal을 문자열로 직렬화 (JSON 전용)"""
        return str(v) if v else None


class BidNoticeDetail(BidNotice):
    """
    입찰공고 상세 정보 모델

    상세 페이지에서 추출 가능한 모든 정보를 담습니다.
    BidNotice를 상속하여 기본 정보 + 추가 정보를 포함합니다.
    """

    # 상세 공고 정보
    bid_method: Optional[str] = Field(default=None, description="입찰 방식")
    contract_method: Optional[str] = Field(default=None, description="계약 방법")
    qualification: Optional[str] = Field(default=None, description="입찰 참가 자격")

    # 지역 정보
    region: Optional[str] = Field(default=None, description="납품/공사 지역")
    delivery_location: Optional[str] = Field(default=None, description="납품 장소")

    # 담당자 정보
    contact_department: Optional[str] = Field(default=None, description="담당 부서")
    contact_person: Optional[str] = Field(default=None, description="담당자명")
    contact_phone: Optional[str] = Field(default=None, description="담당자 연락처")
    contact_email: Optional[str] = Field(default=None, description="담당자 이메일")

    # 첨부 파일
    attachments: List[str] = Field(default_factory=list, description="첨부파일 목록")

    # 추가 메타 정보
    registration_no: Optional[str] = Field(default=None, description="사업자등록번호")
    reference_no: Optional[str] = Field(default=None, description="참조번호")
    raw_html: Optional[str] = Field(default=None, description="원본 HTML (디버깅용)")

    # 크롤링 메타데이터
    detail_crawled_at: Optional[datetime] = Field(default=None, description="상세 페이지 수집 일시")
    crawl_success: bool = Field(default=True, description="상세 크롤링 성공 여부")
    crawl_error: Optional[str] = Field(default=None, description="크롤링 오류 메시지")

    @field_serializer('detail_crawled_at', when_used='json')
    @classmethod
    def serialize_detail_crawled_at(cls, v: Optional[datetime]) -> Optional[str]:
        """detail_crawled_at datetime을 ISO 형식 문자열로 직렬화 (JSON 전용)"""
        return v.isoformat() if v else None

    # === Domain Behaviors ===

    def has_attachments(self) -> bool:
        """
        첨부파일 존재 여부 확인

        Returns:
            첨부파일이 있으면 True
        """
        return len(self.attachments) > 0

    def get_contact_info(self) -> Optional[str]:
        """
        담당자 연락처 포맷팅

        부서, 담당자명, 전화번호를 슬래시로 구분하여 반환합니다.

        Returns:
            포맷된 연락처 문자열 또는 None
        """
        parts = []
        if self.contact_department:
            parts.append(self.contact_department)
        if self.contact_person:
            parts.append(self.contact_person)
        if self.contact_phone:
            parts.append(self.contact_phone)
        return " / ".join(parts) if parts else None

    def is_crawl_complete(self) -> bool:
        """
        크롤링 완료 여부 확인

        상세 크롤링이 성공적으로 완료되었는지 확인합니다.

        Returns:
            성공적으로 크롤링 완료되었으면 True
        """
        return self.crawl_success and self.detail_crawled_at is not None


class BidNoticeList(BaseModel):
    """입찰공고 목록 응답 모델"""

    items: List[BidNotice] = Field(default_factory=list, description="공고 목록")
    total_count: int = Field(default=0, description="전체 공고 수")
    current_page: int = Field(default=1, description="현재 페이지")
    total_pages: int = Field(default=1, description="전체 페이지 수")
    has_next: bool = Field(default=False, description="다음 페이지 존재 여부")
