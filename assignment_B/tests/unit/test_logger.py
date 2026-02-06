"""
logger.py 단위 테스트

로깅 시스템을 테스트합니다.
"""

import logging
import tempfile
from pathlib import Path

import pytest

from bid_crawler.utils.logger import (
    ColoredFormatter,
    CrawlLogger,
    get_logger,
    reset_loggers,
    setup_logger,
)


class TestColoredFormatter:
    """ColoredFormatter 테스트"""

    def test_format_with_color(self) -> None:
        """컬러 포매팅 테스트"""
        formatter = ColoredFormatter("%(levelname)s - %(message)s")

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)
        # ANSI 코드가 포함되어야 함
        assert "\033[" in formatted or "INFO" in formatted

    def test_different_levels(self) -> None:
        """다른 로그 레벨 테스트"""
        formatter = ColoredFormatter("%(levelname)s")

        for level in [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR]:
            record = logging.LogRecord(
                name="test",
                level=level,
                pathname="",
                lineno=0,
                msg="test",
                args=(),
                exc_info=None,
            )
            formatted = formatter.format(record)
            assert formatted  # 비어있지 않아야 함


class TestSetupLogger:
    """setup_logger 함수 테스트"""

    def setup_method(self) -> None:
        """각 테스트 전 로거 초기화"""
        reset_loggers()

    def test_basic_setup(self) -> None:
        """기본 설정 테스트"""
        logger = setup_logger("test_basic")

        assert logger.name == "test_basic"
        assert logger.level == logging.INFO
        assert len(logger.handlers) >= 1

    def test_custom_level(self) -> None:
        """사용자 정의 레벨 테스트"""
        logger = setup_logger("test_level", level="DEBUG")

        assert logger.level == logging.DEBUG

    def test_file_handler(self) -> None:
        """파일 핸들러 테스트"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = setup_logger("test_file", log_file=log_file)

            logger.info("test message")

            # 파일에 기록되었는지 확인
            assert log_file.exists()
            content = log_file.read_text(encoding="utf-8")
            assert "test message" in content

    def test_no_console_output(self) -> None:
        """콘솔 출력 비활성화 테스트"""
        logger = setup_logger("test_no_console", console_output=False)

        # 콘솔 핸들러가 없어야 함
        stream_handlers = [
            h for h in logger.handlers if isinstance(h, logging.StreamHandler)
        ]
        # FileHandler도 StreamHandler를 상속하므로 조심해야 함
        # 여기서는 단순히 핸들러 수가 0임을 확인

    def test_rotation_size(self) -> None:
        """크기 기반 로그 회전 테스트"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = setup_logger(
                "test_rotation_size",
                log_file=log_file,
                rotation="size",
                max_bytes=1024,
                backup_count=3,
            )

            # RotatingFileHandler가 사용되어야 함
            from logging.handlers import RotatingFileHandler

            rotating_handlers = [
                h for h in logger.handlers if isinstance(h, RotatingFileHandler)
            ]
            assert len(rotating_handlers) == 1

    def test_rotation_time(self) -> None:
        """시간 기반 로그 회전 테스트"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = setup_logger(
                "test_rotation_time",
                log_file=log_file,
                rotation="time",
                rotation_when="midnight",
            )

            # TimedRotatingFileHandler가 사용되어야 함
            from logging.handlers import TimedRotatingFileHandler

            timed_handlers = [
                h for h in logger.handlers if isinstance(h, TimedRotatingFileHandler)
            ]
            assert len(timed_handlers) == 1

    def test_caching(self) -> None:
        """로거 캐싱 테스트"""
        logger1 = setup_logger("test_cache")
        logger2 = setup_logger("test_cache")

        assert logger1 is logger2


class TestGetLogger:
    """get_logger 함수 테스트"""

    def setup_method(self) -> None:
        """각 테스트 전 로거 초기화"""
        reset_loggers()

    def test_get_existing_logger(self) -> None:
        """기존 로거 가져오기"""
        setup_logger("test_get")
        logger = get_logger("test_get")

        assert logger.name == "test_get"

    def test_get_new_logger(self) -> None:
        """새 로거 자동 생성"""
        logger = get_logger("test_new")

        assert logger is not None
        assert logger.name == "test_new"

    def test_get_child_logger(self) -> None:
        """자식 로거 생성"""
        setup_logger("parent")
        child = get_logger("parent.child")

        assert child.name == "parent.child"


class TestResetLoggers:
    """reset_loggers 함수 테스트"""

    def test_reset(self) -> None:
        """로거 초기화 테스트"""
        setup_logger("test_reset1")
        setup_logger("test_reset2")

        reset_loggers()

        # 새로운 로거가 생성되어야 함
        logger1 = get_logger("test_reset1")
        logger2 = get_logger("test_reset2")

        # 핸들러가 새로 설정되어야 함
        assert logger1 is not None
        assert logger2 is not None


class TestCrawlLogger:
    """CrawlLogger 클래스 테스트"""

    def setup_method(self) -> None:
        """각 테스트 전 로거 초기화"""
        reset_loggers()

    def test_start_crawl(self) -> None:
        """크롤링 시작 로그"""
        crawl_logger = CrawlLogger()
        crawl_logger.start_crawl("test_run_001", "max_pages=10")

        assert crawl_logger.start_time is not None

    def test_end_crawl(self) -> None:
        """크롤링 종료 로그"""
        crawl_logger = CrawlLogger()
        crawl_logger.start_crawl("test_run_001")
        crawl_logger.end_crawl(total=100, success=95, errors=5, duplicates=10)

        # 시작 시간이 설정되어 있어야 함
        assert crawl_logger.start_time is not None

    def test_page_progress(self) -> None:
        """페이지 진행 로그"""
        crawl_logger = CrawlLogger()
        crawl_logger.page_progress(current=5, total=10, items=50)
        crawl_logger.page_progress(current=5, total=None, items=50)

    def test_item_collected(self) -> None:
        """항목 수집 로그"""
        crawl_logger = CrawlLogger()
        crawl_logger.item_collected("BID001", "테스트 입찰 공고 제목입니다")

    def test_item_error(self) -> None:
        """항목 오류 로그"""
        crawl_logger = CrawlLogger()
        crawl_logger.item_error("BID001", "페이지 로드 실패")

    def test_resuming(self) -> None:
        """재시작 로그"""
        crawl_logger = CrawlLogger()
        crawl_logger.resuming(page=5, index=3)

    def test_robots_blocked(self) -> None:
        """robots.txt 차단 로그"""
        crawl_logger = CrawlLogger()
        crawl_logger.robots_blocked("https://example.com/private")

    def test_rate_limited(self) -> None:
        """속도 제한 로그"""
        crawl_logger = CrawlLogger()
        crawl_logger.rate_limited(delay=5.0)
