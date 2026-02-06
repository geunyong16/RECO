"""
도메인 모델 행동 테스트

BidNotice의 도메인 로직과 Decimal 타입 변환을 검증합니다.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta

from bid_crawler.models.bid_notice import BidNotice, BidNoticeDetail, BidType, BidStatus
from bid_crawler.exceptions import InvalidBidDataException


class TestBidNoticeDomainBehavior:
    """BidNotice 도메인 행동 테스트"""

    def test_is_valuable_above_threshold(self, valuable_bid):
        """기준 이상 가치 판단"""
        assert valuable_bid.is_valuable() is True
        assert valuable_bid.is_valuable(Decimal("100000000")) is True

    def test_is_valuable_below_threshold(self, low_value_bid):
        """기준 미만 가치 판단"""
        assert low_value_bid.is_valuable() is False
        # 커스텀 임계값으로는 True
        assert low_value_bid.is_valuable(Decimal("30000000")) is True

    def test_is_valuable_no_price(self, no_price_bid):
        """가격 없는 경우"""
        assert no_price_bid.is_valuable() is False

    def test_is_open(self, sample_bid_notice):
        """공고중 상태 확인"""
        assert sample_bid_notice.is_open() is True

        closed = sample_bid_notice.model_copy(update={"status": BidStatus.CLOSED})
        assert closed.is_open() is False

    def test_is_expired(self, expired_bid):
        """마감 여부 확인"""
        assert expired_bid.is_expired() is True

    def test_is_not_expired(self, valuable_bid):
        """미마감 확인"""
        assert valuable_bid.is_expired() is False

    def test_is_expired_no_deadline(self, no_price_bid):
        """마감일 없는 경우"""
        assert no_price_bid.is_expired() is False

    def test_can_participate_open_and_not_expired(self, valuable_bid):
        """참가 가능 - 공고중 + 미마감"""
        assert valuable_bid.can_participate() is True

    def test_cannot_participate_expired(self, expired_bid):
        """참가 불가 - 마감됨"""
        assert expired_bid.can_participate() is False

    def test_cannot_participate_closed(self, sample_bid_notice):
        """참가 불가 - 공고 종료"""
        closed = sample_bid_notice.model_copy(update={"status": BidStatus.CLOSED})
        assert closed.can_participate() is False

    def test_transition_to_valid_closed(self, sample_bid_notice):
        """유효한 상태 전환 - OPEN -> CLOSED"""
        closed = sample_bid_notice.transition_to(BidStatus.CLOSED)
        assert closed.status == BidStatus.CLOSED
        # 원본 불변 확인
        assert sample_bid_notice.status == BidStatus.OPEN

    def test_transition_to_valid_cancelled(self, sample_bid_notice):
        """유효한 상태 전환 - OPEN -> CANCELLED"""
        cancelled = sample_bid_notice.transition_to(BidStatus.CANCELLED)
        assert cancelled.status == BidStatus.CANCELLED

    def test_transition_to_valid_postponed(self, sample_bid_notice):
        """유효한 상태 전환 - OPEN -> POSTPONED"""
        postponed = sample_bid_notice.transition_to(BidStatus.POSTPONED)
        assert postponed.status == BidStatus.POSTPONED

    def test_transition_to_invalid(self, sample_bid_notice):
        """무효한 상태 전환"""
        with pytest.raises(InvalidBidDataException):
            # OPEN -> REBID 불가
            sample_bid_notice.transition_to(BidStatus.REBID)

    def test_transition_from_postponed(self):
        """POSTPONED에서의 전환"""
        bid = BidNotice(
            bid_notice_id="test",
            title="Test",
            status=BidStatus.POSTPONED,
        )
        # POSTPONED -> OPEN 가능
        reopened = bid.transition_to(BidStatus.OPEN)
        assert reopened.status == BidStatus.OPEN

        # POSTPONED -> REBID 가능
        rebid = bid.transition_to(BidStatus.REBID)
        assert rebid.status == BidStatus.REBID

    def test_get_price_display_eok(self, valuable_bid):
        """가격 표시 - 억 단위"""
        display = valuable_bid.get_price_display()
        assert "5억" in display

    def test_get_price_display_man(self, low_value_bid):
        """가격 표시 - 만원 단위"""
        display = low_value_bid.get_price_display()
        assert "만원" in display

    def test_get_price_display_no_price(self, no_price_bid):
        """가격 표시 - 가격 없음"""
        display = no_price_bid.get_price_display()
        assert display == "미정"


class TestDecimalConversion:
    """Decimal 변환 테스트"""

    def test_int_to_decimal(self):
        """int -> Decimal 변환"""
        bid = BidNotice(
            bid_notice_id="test",
            title="Test",
            estimated_price=100000000,  # int
        )
        assert isinstance(bid.estimated_price, Decimal)
        assert bid.estimated_price == Decimal("100000000")

    def test_float_to_decimal(self):
        """float -> Decimal 변환"""
        bid = BidNotice(
            bid_notice_id="test",
            title="Test",
            estimated_price=100000000.50,  # float
        )
        assert isinstance(bid.estimated_price, Decimal)

    def test_string_to_decimal(self):
        """str -> Decimal 변환"""
        bid = BidNotice(
            bid_notice_id="test",
            title="Test",
            estimated_price="100000000",  # str
        )
        assert isinstance(bid.estimated_price, Decimal)
        assert bid.estimated_price == Decimal("100000000")

    def test_decimal_to_decimal(self):
        """Decimal -> Decimal (그대로 유지)"""
        bid = BidNotice(
            bid_notice_id="test",
            title="Test",
            estimated_price=Decimal("100000000"),
        )
        assert isinstance(bid.estimated_price, Decimal)
        assert bid.estimated_price == Decimal("100000000")

    def test_none_stays_none(self):
        """None은 None 유지"""
        bid = BidNotice(
            bid_notice_id="test",
            title="Test",
            estimated_price=None,
        )
        assert bid.estimated_price is None

    def test_invalid_value_raises_exception(self):
        """잘못된 값은 예외 발생"""
        with pytest.raises(InvalidBidDataException):
            BidNotice(
                bid_notice_id="test",
                title="Test",
                estimated_price="invalid",
            )

    def test_base_price_conversion(self):
        """base_price도 Decimal 변환"""
        bid = BidNotice(
            bid_notice_id="test",
            title="Test",
            base_price=95000000,  # int
        )
        assert isinstance(bid.base_price, Decimal)
        assert bid.base_price == Decimal("95000000")


class TestBidNoticeDetailDomainBehavior:
    """BidNoticeDetail 도메인 행동 테스트"""

    def test_has_attachments_true(self, sample_bid_detail):
        """첨부파일 있음"""
        assert sample_bid_detail.has_attachments() is True

    def test_has_attachments_false(self, sample_bid_notice):
        """첨부파일 없음"""
        detail = BidNoticeDetail(
            **sample_bid_notice.model_dump(),
            attachments=[],
        )
        assert detail.has_attachments() is False

    def test_get_contact_info_full(self, sample_bid_detail):
        """연락처 정보 - 전체"""
        contact = sample_bid_detail.get_contact_info()
        assert contact is not None
        assert "구매팀" in contact
        assert "홍길동" in contact
        assert "02-1234-5678" in contact

    def test_get_contact_info_partial(self, sample_bid_notice):
        """연락처 정보 - 일부만"""
        detail = BidNoticeDetail(
            **sample_bid_notice.model_dump(),
            contact_phone="02-1234-5678",
        )
        contact = detail.get_contact_info()
        assert contact == "02-1234-5678"

    def test_get_contact_info_none(self, sample_bid_notice):
        """연락처 정보 - 없음"""
        detail = BidNoticeDetail(**sample_bid_notice.model_dump())
        contact = detail.get_contact_info()
        assert contact is None

    def test_is_crawl_complete_true(self, sample_bid_detail):
        """크롤링 완료 확인 - 성공"""
        assert sample_bid_detail.is_crawl_complete() is True

    def test_is_crawl_complete_false_no_crawled_at(self, sample_bid_notice):
        """크롤링 완료 확인 - 크롤링 안됨"""
        detail = BidNoticeDetail(
            **sample_bid_notice.model_dump(),
            crawl_success=True,
            detail_crawled_at=None,
        )
        assert detail.is_crawl_complete() is False

    def test_is_crawl_complete_false_failed(self, sample_bid_notice):
        """크롤링 완료 확인 - 실패"""
        detail = BidNoticeDetail(
            **sample_bid_notice.model_dump(),
            crawl_success=False,
            detail_crawled_at=datetime.now(),
        )
        assert detail.is_crawl_complete() is False


class TestBidNoticeJsonSerialization:
    """JSON 직렬화 테스트"""

    def test_decimal_serialization(self, sample_bid_notice):
        """Decimal 직렬화"""
        json_data = sample_bid_notice.model_dump_json()
        # Decimal이 문자열로 직렬화되어야 함
        assert '"100000000"' in json_data or '100000000' in json_data

    def test_datetime_serialization(self, sample_bid_notice):
        """datetime 직렬화"""
        json_data = sample_bid_notice.model_dump_json()
        # ISO 형식 확인
        assert "2024-01-31" in json_data

    def test_model_dump_decimal(self, sample_bid_notice):
        """model_dump에서 Decimal 타입 유지"""
        data = sample_bid_notice.model_dump()
        # model_dump는 Decimal 타입 유지
        assert isinstance(data["estimated_price"], Decimal)
