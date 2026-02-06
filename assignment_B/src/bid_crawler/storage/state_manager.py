"""
상태 관리자 모듈

크롤링 상태를 파일로 저장/로드하여 중단점에서 재시작할 수 있도록 합니다.
"""

import json
import shutil
from pathlib import Path
from typing import Optional
from datetime import datetime

from bid_crawler.models.crawl_state import CrawlState, CrawlProgress, CrawlStatistics
from bid_crawler.utils.logger import get_logger

logger = get_logger(__name__)


class StateManager:
    """
    크롤링 상태 관리자

    상태 파일을 통해 크롤링 진행 상황을 영속화합니다.
    오류 발생 시에도 마지막 성공 지점부터 재시작할 수 있습니다.
    """

    def __init__(self, state_file: Path):
        """
        Args:
            state_file: 상태 파일 경로
        """
        self.state_file = Path(state_file)
        self.backup_file = self.state_file.with_suffix(".backup.json")
        self._state: Optional[CrawlState] = None

    @property
    def state(self) -> CrawlState:
        """현재 상태 (없으면 새로 생성)"""
        if self._state is None:
            self._state = CrawlState(
                run_id=datetime.now().strftime("%Y%m%d_%H%M%S")
            )
        return self._state

    def initialize(self, run_id: str, resume: bool = True) -> CrawlState:
        """
        상태 초기화

        Args:
            run_id: 실행 ID
            resume: True면 이전 상태에서 재시작, False면 새로 시작

        Returns:
            초기화된 상태
        """
        if resume and self.state_file.exists():
            loaded = self.load()
            if loaded and not loaded.is_completed:
                logger.info(
                    f"이전 상태에서 재시작: "
                    f"페이지 {loaded.progress.current_page}, "
                    f"수집 {loaded.statistics.total_collected}건"
                )
                self._state = loaded
                self._state.is_running = True
                self._state.run_id = run_id
                return self._state

        # 새 상태 생성
        self._state = CrawlState(
            run_id=run_id,
            is_running=True,
        )
        logger.info(f"새 크롤링 시작: {run_id}")
        return self._state

    def load(self) -> Optional[CrawlState]:
        """
        상태 파일 로드

        Returns:
            로드된 상태 또는 None (파일 없거나 오류 시)
        """
        if not self.state_file.exists():
            logger.debug(f"상태 파일 없음: {self.state_file}")
            return None

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Set 복원
            if "collected_ids" in data:
                data["collected_ids"] = set(data["collected_ids"])

            # 중첩 모델 복원
            if "progress" in data and isinstance(data["progress"], dict):
                data["progress"] = CrawlProgress(**data["progress"])
            if "statistics" in data and isinstance(data["statistics"], dict):
                data["statistics"] = CrawlStatistics(**data["statistics"])

            state = CrawlState(**data)
            logger.info(f"상태 로드 완료: {self.state_file}")
            return state

        except Exception as e:
            logger.error(f"상태 로드 실패: {e}")

            # 백업에서 복원 시도
            if self.backup_file.exists():
                logger.info("백업에서 복원 시도...")
                try:
                    shutil.copy(self.backup_file, self.state_file)
                    return self.load()
                except Exception as be:
                    logger.error(f"백업 복원 실패: {be}")

            return None

    def save(self, force: bool = False) -> bool:
        """
        상태 파일 저장

        Args:
            force: True면 무조건 저장

        Returns:
            저장 성공 여부
        """
        if self._state is None:
            return False

        try:
            # 디렉토리 생성
            self.state_file.parent.mkdir(parents=True, exist_ok=True)

            # 기존 파일 백업
            if self.state_file.exists():
                shutil.copy(self.state_file, self.backup_file)

            # 상태 직렬화
            data = self._state.model_dump()
            data["collected_ids"] = list(self._state.collected_ids)

            # 날짜 직렬화
            for key in ["started_at", "last_updated_at"]:
                if key in data and data[key]:
                    if isinstance(data[key], datetime):
                        data[key] = data[key].isoformat()

            # 저장
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)

            logger.debug(f"상태 저장 완료: {self.state_file}")
            return True

        except Exception as e:
            logger.error(f"상태 저장 실패: {e}")
            return False

    def mark_collected(self, bid_id: str) -> bool:
        """
        ID를 수집 완료로 표시

        Returns:
            True: 신규 수집, False: 중복
        """
        return self.state.mark_collected(bid_id)

    def is_collected(self, bid_id: str) -> bool:
        """이미 수집된 ID인지 확인"""
        return self.state.is_collected(bid_id)

    def update_progress(
        self,
        page: Optional[int] = None,
        index: Optional[int] = None,
        total_pages: Optional[int] = None,
    ) -> None:
        """진행 상황 업데이트"""
        self.state.update_progress(page, index, total_pages)

    def complete_page(self, page: int) -> None:
        """페이지 완료 처리"""
        self.state.complete_page(page)
        self.save()  # 페이지 완료 시 자동 저장

    def record_error(self, error: str, item_info: Optional[dict] = None) -> None:
        """오류 기록"""
        self.state.record_error(error, item_info)

    def record_retry(self) -> None:
        """재시도 기록"""
        self.state.record_retry()

    def mark_completed(self) -> None:
        """크롤링 완료 처리"""
        self.state.mark_completed()
        self.save(force=True)

    def get_resume_point(self) -> tuple:
        """
        재시작 지점 반환

        Returns:
            (page, index): 재시작할 페이지와 인덱스
        """
        return (
            self.state.progress.current_page,
            self.state.progress.current_index,
        )

    def get_statistics(self) -> CrawlStatistics:
        """통계 반환"""
        return self.state.statistics

    def cleanup(self, remove_backup: bool = True) -> None:
        """
        상태 파일 정리

        Args:
            remove_backup: 백업 파일도 삭제할지 여부
        """
        if self.state_file.exists():
            self.state_file.unlink()
            logger.info(f"상태 파일 삭제: {self.state_file}")

        if remove_backup and self.backup_file.exists():
            self.backup_file.unlink()
            logger.debug(f"백업 파일 삭제: {self.backup_file}")

        self._state = None
