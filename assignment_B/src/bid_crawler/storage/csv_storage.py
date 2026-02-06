"""
CSV 저장소 모듈

수집된 데이터를 CSV 형식으로 저장합니다.
"""

import csv
from pathlib import Path
from typing import List, Optional, Union
from datetime import datetime

from bid_crawler.models.bid_notice import BidNotice, BidNoticeDetail
from bid_crawler.utils.logger import get_logger

logger = get_logger(__name__)


class CsvStorage:
    """
    CSV 파일 저장소

    수집된 입찰공고를 CSV 파일로 저장합니다.
    엑셀에서 쉽게 열 수 있도록 UTF-8 BOM을 포함합니다.
    """

    # CSV 컬럼 정의
    COLUMNS = [
        ("bid_notice_id", "공고번호"),
        ("title", "공고명"),
        ("bid_type", "입찰유형"),
        ("status", "상태"),
        ("organization", "공고기관"),
        ("demand_organization", "수요기관"),
        ("announce_date", "공고일시"),
        ("deadline", "마감일시"),
        ("estimated_price", "추정가격"),
        ("base_price", "기초금액"),
        ("bid_method", "입찰방식"),
        ("contract_method", "계약방법"),
        ("qualification", "참가자격"),
        ("region", "지역"),
        ("delivery_location", "납품장소"),
        ("contact_department", "담당부서"),
        ("contact_person", "담당자"),
        ("contact_phone", "연락처"),
        ("contact_email", "이메일"),
        ("detail_url", "상세URL"),
        ("crawled_at", "수집일시"),
    ]

    def __init__(
        self,
        output_dir: Path,
        filename: str = "bid_notices.csv",
        include_header: bool = True,
        use_korean_header: bool = True,
    ):
        """
        Args:
            output_dir: 출력 디렉토리
            filename: 출력 파일명
            include_header: 헤더 포함 여부
            use_korean_header: 한글 헤더 사용 여부
        """
        self.output_dir = Path(output_dir)
        self.filename = filename
        self.include_header = include_header
        self.use_korean_header = use_korean_header
        self._initialized = False

        # 디렉토리 생성
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def output_file(self) -> Path:
        """출력 파일 경로"""
        return self.output_dir / self.filename

    @property
    def headers(self) -> List[str]:
        """헤더 목록"""
        if self.use_korean_header:
            return [col[1] for col in self.COLUMNS]
        return [col[0] for col in self.COLUMNS]

    @property
    def field_names(self) -> List[str]:
        """필드명 목록"""
        return [col[0] for col in self.COLUMNS]

    def save(
        self,
        notices: Union[BidNotice, BidNoticeDetail, List[Union[BidNotice, BidNoticeDetail]]],
    ) -> int:
        """
        데이터 저장

        Args:
            notices: 저장할 공고 (단일 또는 리스트)

        Returns:
            저장된 건수
        """
        if not isinstance(notices, list):
            notices = [notices]

        if not notices:
            return 0

        try:
            # 파일 초기화 (헤더 작성)
            if not self._initialized:
                self._initialize_file()

            # 추가 모드로 데이터 작성
            with open(self.output_file, "a", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)

                for notice in notices:
                    row = self._to_row(notice)
                    writer.writerow(row)

            logger.debug(f"CSV 저장: {len(notices)}건")
            return len(notices)

        except Exception as e:
            logger.error(f"CSV 저장 실패: {e}")
            return 0

    def _initialize_file(self) -> None:
        """파일 초기화 (헤더 작성)"""
        # 파일이 이미 존재하고 내용이 있으면 초기화 건너뜀
        if self.output_file.exists() and self.output_file.stat().st_size > 0:
            self._initialized = True
            return

        try:
            with open(self.output_file, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                if self.include_header:
                    writer.writerow(self.headers)

            self._initialized = True
            logger.info(f"CSV 파일 생성: {self.output_file}")

        except Exception as e:
            logger.error(f"CSV 초기화 실패: {e}")
            raise

    def _to_row(self, notice: Union[BidNotice, BidNoticeDetail]) -> List[str]:
        """모델을 CSV 행으로 변환"""
        data = notice.model_dump()
        row = []

        for field_name, _ in self.COLUMNS:
            value = data.get(field_name, "")

            # 타입 변환
            if value is None:
                value = ""
            elif isinstance(value, datetime):
                value = value.strftime("%Y-%m-%d %H:%M:%S")
            elif isinstance(value, (int, float)):
                value = str(value)
            elif hasattr(value, "value"):  # Enum
                value = value.value
            elif isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            else:
                value = str(value)

            row.append(value)

        return row

    def load(self) -> List[dict]:
        """저장된 데이터 로드"""
        if not self.output_file.exists():
            return []

        try:
            data = []
            with open(self.output_file, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)

                # 헤더 매핑 (한글 -> 영문)
                header_map = {col[1]: col[0] for col in self.COLUMNS}

                for row in reader:
                    # 한글 헤더를 영문으로 변환
                    converted_row = {}
                    for key, value in row.items():
                        eng_key = header_map.get(key, key)
                        converted_row[eng_key] = value
                    data.append(converted_row)

            return data

        except Exception as e:
            logger.error(f"CSV 로드 실패: {e}")
            return []

    def count(self) -> int:
        """저장된 데이터 건수 (헤더 제외)"""
        if not self.output_file.exists():
            return 0

        try:
            with open(self.output_file, "r", encoding="utf-8-sig") as f:
                # 헤더 제외
                return sum(1 for _ in f) - (1 if self.include_header else 0)
        except Exception:
            return 0

    def close(self) -> None:
        """저장소 종료"""
        pass  # CSV는 매번 플러시되므로 별도 작업 불필요
