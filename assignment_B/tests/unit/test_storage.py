"""
저장소 모듈 테스트

StateManager, JsonStorage, CsvStorage의 동작을 검증합니다.
"""

import pytest
import json
from pathlib import Path

from bid_crawler.storage.state_manager import StateManager
from bid_crawler.storage.json_storage import JsonStorage
from bid_crawler.storage.csv_storage import CsvStorage
from bid_crawler.models.crawl_state import CrawlState


class TestStateManager:
    """StateManager 테스트"""

    @pytest.fixture
    def state_manager(self, tmp_path: Path) -> StateManager:
        """테스트용 StateManager"""
        return StateManager(tmp_path / "state.json")

    def test_initialize_new(self, state_manager):
        """새 상태 초기화"""
        state = state_manager.initialize("test_run", resume=False)
        assert state.run_id == "test_run"
        assert state.is_running is True

    def test_save_and_load(self, state_manager):
        """저장 및 로드"""
        state = state_manager.initialize("test_run", resume=False)
        state_manager.mark_collected("id1")
        state_manager.mark_collected("id2")
        state_manager.save()

        # 새 매니저로 로드
        new_manager = StateManager(state_manager.state_file)
        loaded = new_manager.load()

        assert loaded is not None
        assert loaded.run_id == "test_run"
        assert "id1" in loaded.collected_ids
        assert "id2" in loaded.collected_ids

    def test_resume_from_previous(self, state_manager, tmp_path):
        """이전 상태에서 재시작"""
        # 이전 상태 생성
        state = state_manager.initialize("old_run", resume=False)
        state_manager.update_progress(page=5, index=3)
        state_manager.save()

        # 새 실행으로 재시작
        new_manager = StateManager(state_manager.state_file)
        resumed = new_manager.initialize("new_run", resume=True)

        assert resumed.progress.current_page == 5
        assert resumed.progress.current_index == 3

    def test_cleanup(self, state_manager):
        """상태 파일 정리"""
        state_manager.initialize("test", resume=False)
        state_manager.save()

        assert state_manager.state_file.exists()
        state_manager.cleanup()
        assert not state_manager.state_file.exists()


class TestJsonStorage:
    """JsonStorage 테스트"""

    @pytest.fixture
    def json_storage(self, tmp_path: Path) -> JsonStorage:
        """테스트용 JsonStorage"""
        return JsonStorage(tmp_path)

    def test_save_single(self, json_storage, sample_bid_detail):
        """단일 항목 저장"""
        result = json_storage.save(sample_bid_detail)
        json_storage.flush()

        assert result is True  # save() returns bool now
        assert json_storage.output_file.exists()

    def test_save_multiple(self, json_storage, sample_notices):
        """다중 항목 저장 (save_batch 사용)"""
        count = json_storage.save_batch(sample_notices)  # use save_batch for multiple items
        json_storage.flush()

        assert count == 5

        # 내용 확인
        data = json_storage.load()
        assert len(data) == 5

    def test_incremental_save(self, json_storage, sample_notices):
        """증분 저장"""
        # 첫 번째 저장
        json_storage.save_batch(sample_notices[:3])  # use save_batch
        json_storage.flush()

        # 두 번째 저장
        json_storage.save_batch(sample_notices[3:])  # use save_batch
        json_storage.flush()

        data = json_storage.load()
        assert len(data) == 5

    def test_deduplication(self, json_storage, sample_bid_detail):
        """중복 제거"""
        json_storage.save(sample_bid_detail)
        json_storage.flush()

        # 같은 ID로 다시 저장 - returns False for duplicate
        result = json_storage.save(sample_bid_detail)
        json_storage.flush()

        assert result is False  # duplicate returns False
        data = json_storage.load()
        assert len(data) == 1

    def test_exists(self, json_storage, sample_bid_detail):
        """존재 여부 확인"""
        assert json_storage.exists(sample_bid_detail.bid_notice_id) is False

        json_storage.save(sample_bid_detail)

        assert json_storage.exists(sample_bid_detail.bid_notice_id) is True

    def test_find_by_id(self, json_storage, sample_bid_detail):
        """ID로 조회"""
        json_storage.save(sample_bid_detail)
        json_storage.flush()

        found = json_storage.find_by_id(sample_bid_detail.bid_notice_id)
        assert found is not None
        assert found.bid_notice_id == sample_bid_detail.bid_notice_id

    def test_count(self, json_storage, sample_notices):
        """건수 확인"""
        assert json_storage.count() == 0

        json_storage.save_batch(sample_notices)

        assert json_storage.count() == 5


class TestCsvStorage:
    """CsvStorage 테스트"""

    @pytest.fixture
    def csv_storage(self, tmp_path: Path) -> CsvStorage:
        """테스트용 CsvStorage"""
        return CsvStorage(tmp_path)

    def test_save_with_header(self, csv_storage, sample_bid_detail):
        """헤더 포함 저장"""
        csv_storage.save(sample_bid_detail)

        # 파일 내용 확인
        content = csv_storage.output_file.read_text(encoding="utf-8-sig")
        assert "공고번호" in content  # 한글 헤더
        assert "20240115-001" in content

    def test_save_multiple(self, csv_storage, sample_notices):
        """다중 항목 저장"""
        count = csv_storage.save(sample_notices)
        assert count == 5
        assert csv_storage.count() == 5

    def test_load(self, csv_storage, sample_notices):
        """로드"""
        csv_storage.save(sample_notices)
        data = csv_storage.load()

        assert len(data) == 5
        assert "bid_notice_id" in data[0]  # 영문 키로 변환됨
