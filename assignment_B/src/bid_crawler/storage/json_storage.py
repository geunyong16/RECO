"""
JSON 저장소 모듈

수집된 데이터를 JSON 형식으로 저장합니다.
BidRepository 인터페이스를 구현하며 Decimal 타입을 지원합니다.
"""

import json
from pathlib import Path
from typing import List, Optional, Union, Type, TypeVar
from datetime import datetime
from decimal import Decimal

from bid_crawler.models.bid_notice import BidNotice, BidNoticeDetail
from bid_crawler.exceptions import DuplicateBidException, RepositoryException
from bid_crawler.utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T', bound=BidNotice)


class DecimalEncoder(json.JSONEncoder):
    """
    Decimal 타입 JSON 인코더

    Decimal과 datetime 타입을 JSON 직렬화 가능한 형식으로 변환합니다.
    """

    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class JsonStorage:
    """
    JSON 파일 저장소

    BidRepository 인터페이스를 구현합니다.
    수집된 입찰공고를 JSON 파일로 저장합니다.

    Features:
        - 단일 파일: 모든 데이터를 하나의 JSON 배열로
        - 개별 파일: 각 공고를 별도 파일로
        - 증분 저장: 기존 파일에 추가
        - Decimal 직렬화: 정밀도 보장
        - ID 캐시: 메모리에서 빠른 중복 확인

    Examples:
        >>> storage = JsonStorage(Path("./data"))
        >>> storage.save(bid_detail)
        True
        >>> storage.exists("12345")
        True
    """

    def __init__(
        self,
        output_dir: Path,
        filename: str = "bid_notices.json",
        individual_files: bool = False,
        pretty: bool = True,
        model_class: Type[T] = BidNoticeDetail,
        raise_on_duplicate: bool = False,
    ):
        """
        Args:
            output_dir: 출력 디렉토리
            filename: 출력 파일명 (단일 파일 모드)
            individual_files: 개별 파일 모드 사용 여부
            pretty: 들여쓰기 적용 여부
            model_class: 역직렬화에 사용할 모델 클래스
            raise_on_duplicate: 중복 시 예외 발생 여부
        """
        self.output_dir = Path(output_dir)
        self.filename = filename
        self.individual_files = individual_files
        self.pretty = pretty
        self.model_class = model_class
        self.raise_on_duplicate = raise_on_duplicate
        self._buffer: List[dict] = []
        self._id_cache: set = set()  # 메모리 ID 캐시

        # 디렉토리 생성
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 기존 데이터에서 ID 캐시 로드
        self._load_id_cache()

    def _load_id_cache(self) -> None:
        """기존 데이터에서 ID 캐시 로드"""
        try:
            existing = self._load_raw()
            self._id_cache = {item.get("bid_notice_id") for item in existing if item.get("bid_notice_id")}
            logger.debug(f"ID cache loaded: {len(self._id_cache)} items")
        except Exception as e:
            logger.warning(f"Failed to load ID cache: {e}")
            self._id_cache = set()

    @property
    def output_file(self) -> Path:
        """단일 파일 경로"""
        return self.output_dir / self.filename

    # === BidRepository Interface Implementation ===

    def save(self, bid: Union[BidNotice, BidNoticeDetail]) -> bool:
        """
        단일 입찰공고 저장

        BidRepository 인터페이스 구현입니다.

        Args:
            bid: 저장할 입찰공고

        Returns:
            저장 성공 여부

        Raises:
            DuplicateBidException: raise_on_duplicate=True이고 중복인 경우
        """
        bid_id = bid.bid_notice_id

        if self.exists(bid_id):
            if self.raise_on_duplicate:
                raise DuplicateBidException(bid_id)
            logger.debug(f"Skipping duplicate: {bid_id}")
            return False

        if self.individual_files:
            success = self._save_individual(bid)
            if success:
                self._id_cache.add(bid_id)
            return success
        else:
            self._buffer.append(self._to_dict(bid))
            self._id_cache.add(bid_id)

            # 버퍼가 일정 크기 이상이면 플러시
            if len(self._buffer) >= 10:
                self.flush()
            return True

    def save_batch(self, bids: List[Union[BidNotice, BidNoticeDetail]]) -> int:
        """
        다중 입찰공고 배치 저장

        BidRepository 인터페이스 구현입니다.

        Args:
            bids: 저장할 입찰공고 리스트

        Returns:
            실제로 저장된 건수
        """
        count = 0
        for bid in bids:
            try:
                if self.save(bid):
                    count += 1
            except DuplicateBidException:
                continue
        return count

    def exists(self, bid_id: str) -> bool:
        """
        ID 존재 여부 확인

        BidRepository 인터페이스 구현입니다.
        메모리 캐시를 사용하여 빠르게 확인합니다.

        Args:
            bid_id: 입찰공고 ID

        Returns:
            존재하면 True
        """
        return bid_id in self._id_cache

    def find_by_id(self, bid_id: str) -> Optional[BidNoticeDetail]:
        """
        ID로 입찰공고 조회

        BidRepository 인터페이스 구현입니다.

        Args:
            bid_id: 입찰공고 ID

        Returns:
            조회된 입찰공고 또는 None
        """
        # 버퍼에서 먼저 확인
        for item in self._buffer:
            if item.get("bid_notice_id") == bid_id:
                return self._from_dict(item)

        # 파일에서 확인
        data = self._load_raw()
        for item in data:
            if item.get("bid_notice_id") == bid_id:
                return self._from_dict(item)

        return None

    def find_all(self, limit: Optional[int] = None) -> List[BidNoticeDetail]:
        """
        모든 입찰공고 조회

        BidRepository 인터페이스 구현입니다.

        Args:
            limit: 최대 조회 건수

        Returns:
            입찰공고 리스트
        """
        data = self._load_raw()

        # 버퍼 내용도 포함
        buffer_ids = {item.get("bid_notice_id") for item in data}
        for item in self._buffer:
            if item.get("bid_notice_id") not in buffer_ids:
                data.append(item)

        if limit:
            data = data[:limit]

        return [self._from_dict(item) for item in data]

    def count(self) -> int:
        """
        저장된 데이터 건수

        BidRepository 인터페이스 구현입니다.
        """
        return len(self._id_cache)

    def flush(self) -> bool:
        """
        버퍼 플러시 (단일 파일 모드)

        BidRepository 인터페이스 구현입니다.
        기존 파일이 있으면 병합합니다.
        """
        if not self._buffer:
            return True

        try:
            # 기존 데이터 로드
            existing_data = self._load_raw()

            # 중복 제거 후 병합
            existing_ids = {item.get("bid_notice_id") for item in existing_data}
            new_items = [
                item for item in self._buffer
                if item.get("bid_notice_id") not in existing_ids
            ]

            all_data = existing_data + new_items

            # 저장
            with open(self.output_file, "w", encoding="utf-8") as f:
                json.dump(
                    all_data,
                    f,
                    ensure_ascii=False,
                    indent=2 if self.pretty else None,
                    cls=DecimalEncoder,
                )

            logger.info(f"JSON saved: {len(new_items)} new (total {len(all_data)})")
            self._buffer = []
            return True

        except Exception as e:
            raise RepositoryException(f"Flush failed: {e}")

    def close(self) -> None:
        """
        저장소 종료 (버퍼 플러시)

        BidRepository 인터페이스 구현입니다.
        """
        self.flush()

    # === 레거시 호환 메서드 ===

    def load(self) -> List[dict]:
        """
        저장된 데이터 로드 (레거시)

        하위 호환성을 위해 유지합니다.
        새 코드에서는 find_all()을 사용하세요.

        Returns:
            딕셔너리 리스트
        """
        return self._load_raw()

    # === 내부 헬퍼 메서드 ===

    def _to_dict(self, notice: Union[BidNotice, BidNoticeDetail]) -> dict:
        """
        모델을 딕셔너리로 변환

        Decimal과 datetime을 문자열로 변환합니다.

        Args:
            notice: 변환할 모델

        Returns:
            딕셔너리
        """
        data = notice.model_dump()

        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            elif isinstance(value, Decimal):
                data[key] = str(value)

        return data

    def _from_dict(self, data: dict) -> BidNoticeDetail:
        """
        딕셔너리에서 모델 복원

        문자열을 Decimal과 datetime으로 복원합니다.

        Args:
            data: 원본 딕셔너리

        Returns:
            복원된 모델
        """
        # 복사본 생성
        data = dict(data)

        # Decimal 필드 복원
        for field in ['estimated_price', 'base_price']:
            if field in data and data[field] is not None:
                try:
                    data[field] = Decimal(str(data[field]))
                except Exception:
                    data[field] = None

        # datetime 필드 복원
        datetime_fields = ['crawled_at', 'announce_date', 'deadline', 'detail_crawled_at']
        for field in datetime_fields:
            if field in data and data[field] is not None:
                try:
                    if isinstance(data[field], str):
                        data[field] = datetime.fromisoformat(data[field])
                except Exception:
                    data[field] = None

        return self.model_class(**data)

    def _load_raw(self) -> List[dict]:
        """
        원시 JSON 데이터 로드

        Returns:
            딕셔너리 리스트
        """
        if self.individual_files:
            return self._load_individual_raw()
        else:
            return self._load_single_raw()

    def _load_single_raw(self) -> List[dict]:
        """단일 파일에서 원시 데이터 로드"""
        if not self.output_file.exists():
            return []

        try:
            with open(self.output_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else [data]
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error, returning empty: {e}")
            return []
        except Exception as e:
            logger.error(f"Load failed: {e}")
            return []

    def _load_individual_raw(self) -> List[dict]:
        """개별 파일에서 원시 데이터 로드"""
        data = []
        for filepath in self.output_dir.glob("*.json"):
            if filepath.name == self.filename:
                continue
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data.append(json.load(f))
            except Exception as e:
                logger.warning(f"File load failed ({filepath}): {e}")
        return data

    def _save_individual(self, notice: Union[BidNotice, BidNoticeDetail]) -> bool:
        """개별 파일로 저장"""
        try:
            filename = f"{notice.bid_notice_id}.json"
            filepath = self.output_dir / filename
            data = self._to_dict(notice)

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(
                    data,
                    f,
                    ensure_ascii=False,
                    indent=2 if self.pretty else None,
                    cls=DecimalEncoder,
                )

            logger.debug(f"Saved: {filepath}")
            return True

        except Exception as e:
            raise RepositoryException(f"Save failed ({notice.bid_notice_id}): {e}")
