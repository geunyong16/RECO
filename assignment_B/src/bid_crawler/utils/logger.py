"""
로깅 설정 모듈

구조화된 로그 출력과 파일 저장을 제공합니다.
로그 회전(rotation) 기능과 JSON 형식의 구조화된 로깅을 지원합니다.
ELK 스택과의 통합을 위한 JSON 포매터를 포함합니다.
"""

import json
import logging
import sys
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Literal, Optional


# 전역 로거 저장소
_loggers: dict[str, logging.Logger] = {}


class ColoredFormatter(logging.Formatter):
    """콘솔 출력용 컬러 포매터"""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


class JsonFormatter(logging.Formatter):
    """
    ELK 스택 호환 JSON 포매터

    로그를 JSON 형식으로 출력하여 Elasticsearch, Logstash, Kibana와
    쉽게 통합할 수 있습니다.

    출력 형식:
        {
            "@timestamp": "2024-01-15T14:30:00.123456",
            "level": "INFO",
            "logger": "bid_crawler",
            "message": "크롤링 시작",
            "module": "crawler",
            "function": "run",
            "line": 42,
            "extra": {...}
        }
    """

    def __init__(
        self,
        include_stack_trace: bool = True,
        extra_fields: Optional[dict[str, Any]] = None,
    ):
        """
        Args:
            include_stack_trace: 예외 발생 시 스택 트레이스 포함 여부
            extra_fields: 모든 로그에 추가할 필드
        """
        super().__init__()
        self.include_stack_trace = include_stack_trace
        self.extra_fields = extra_fields or {}

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "@timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # 추가 필드 병합
        log_data.update(self.extra_fields)

        # LogRecord의 extra 필드 추출
        standard_attrs = {
            "name", "msg", "args", "created", "filename", "funcName",
            "levelname", "levelno", "lineno", "module", "msecs",
            "pathname", "process", "processName", "relativeCreated",
            "stack_info", "exc_info", "exc_text", "thread", "threadName",
            "taskName", "message",
        }

        extra = {}
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                try:
                    json.dumps(value)  # JSON 직렬화 가능 여부 확인
                    extra[key] = value
                except (TypeError, ValueError):
                    extra[key] = str(value)

        if extra:
            log_data["extra"] = extra

        # 예외 정보 추가
        if record.exc_info and self.include_stack_trace:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "stacktrace": traceback.format_exception(*record.exc_info),
            }

        return json.dumps(log_data, ensure_ascii=False, default=str)


def setup_logger(
    name: str = "bid_crawler",
    level: str = "INFO",
    log_file: Optional[Path] = None,
    console_output: bool = True,
    rotation: Literal["size", "time", "none"] = "size",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    rotation_when: str = "midnight",
    json_format: bool = False,
    extra_fields: Optional[dict[str, Any]] = None,
) -> logging.Logger:
    """
    로거 설정

    Args:
        name: 로거 이름
        level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR)
        log_file: 로그 파일 경로 (None이면 파일 출력 안함)
        console_output: 콘솔 출력 여부
        rotation: 로그 회전 방식 ("size", "time", "none")
        max_bytes: size 회전 시 최대 파일 크기 (기본 10MB)
        backup_count: 보관할 백업 파일 수 (기본 5개)
        rotation_when: time 회전 시점 ("midnight", "H", "D", "W0" 등)
        json_format: JSON 형식 로깅 사용 여부 (ELK 스택 통합용)
        extra_fields: JSON 로그에 추가할 필드 (예: {"service": "bid_crawler"})

    Returns:
        설정된 로거
    """
    logger = logging.getLogger(name)

    # 이미 설정된 경우 반환
    if name in _loggers:
        return _loggers[name]

    logger.setLevel(getattr(logging, level.upper()))
    logger.handlers = []  # 기존 핸들러 제거

    # 기본 포맷
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # JSON 포매터 (ELK 스택 통합용)
    json_formatter = JsonFormatter(extra_fields=extra_fields) if json_format else None

    # 콘솔 핸들러
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level.upper()))

        if json_format:
            console_handler.setFormatter(json_formatter)
        elif sys.platform == "win32":
            # Windows에서는 컬러 지원 여부 확인
            try:
                import os

                os.system("")  # Enable ANSI codes on Windows
                console_handler.setFormatter(
                    ColoredFormatter(log_format, datefmt=date_format)
                )
            except Exception:
                console_handler.setFormatter(
                    logging.Formatter(log_format, datefmt=date_format)
                )
        else:
            console_handler.setFormatter(
                ColoredFormatter(log_format, datefmt=date_format)
            )

        logger.addHandler(console_handler)

    # 파일 핸들러 (회전 기능 포함)
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        if rotation == "size":
            # 크기 기반 회전
            file_handler: logging.Handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
        elif rotation == "time":
            # 시간 기반 회전
            file_handler = TimedRotatingFileHandler(
                log_file,
                when=rotation_when,
                backupCount=backup_count,
                encoding="utf-8",
            )
        else:
            # 회전 없음
            file_handler = logging.FileHandler(
                log_file,
                encoding="utf-8",
                mode="a",
            )

        file_handler.setLevel(logging.DEBUG)  # 파일에는 모든 레벨 기록

        # JSON 형식은 파일에도 동일하게 적용
        if json_format:
            file_handler.setFormatter(json_formatter)
        else:
            file_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))

        logger.addHandler(file_handler)

    _loggers[name] = logger
    return logger


def get_logger(name: str = "bid_crawler") -> logging.Logger:
    """
    로거 가져오기

    Args:
        name: 로거 이름

    Returns:
        로거 (없으면 기본 설정으로 생성)
    """
    if name in _loggers:
        return _loggers[name]

    # 부모 로거가 있으면 하위 로거 생성
    if "." in name:
        parent_name = name.rsplit(".", 1)[0]
        if parent_name in _loggers:
            child_logger = logging.getLogger(name)
            _loggers[name] = child_logger
            return child_logger

    # 기본 설정으로 생성
    return setup_logger(name)


def reset_loggers() -> None:
    """모든 로거 초기화 (테스트용)"""
    global _loggers
    for logger in _loggers.values():
        logger.handlers = []
    _loggers.clear()


class CrawlLogger:
    """
    크롤링 전용 로거

    진행 상황, 통계를 구조화된 형태로 로깅합니다.
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self.logger = logger or get_logger("bid_crawler")
        self.start_time: Optional[datetime] = None

    def start_crawl(self, run_id: str, config_summary: str = "") -> None:
        """크롤링 시작 로그"""
        self.start_time = datetime.now()
        self.logger.info("=" * 60)
        self.logger.info(f"크롤링 시작: {run_id}")
        if config_summary:
            self.logger.info(f"설정: {config_summary}")
        self.logger.info("=" * 60)

    def end_crawl(
        self,
        total: int,
        success: int,
        errors: int,
        duplicates: int = 0,
    ) -> None:
        """크롤링 종료 로그"""
        elapsed = ""
        if self.start_time:
            delta = datetime.now() - self.start_time
            elapsed = f" (소요시간: {delta})"

        self.logger.info("=" * 60)
        self.logger.info(f"크롤링 완료{elapsed}")
        self.logger.info(f"  - 전체: {total}건")
        self.logger.info(f"  - 성공: {success}건")
        self.logger.info(f"  - 오류: {errors}건")
        self.logger.info(f"  - 중복 스킵: {duplicates}건")
        self.logger.info("=" * 60)

    def page_progress(self, current: int, total: Optional[int], items: int) -> None:
        """페이지 진행 로그"""
        if total:
            self.logger.info(f"페이지 {current}/{total} 처리 완료 ({items}건 수집)")
        else:
            self.logger.info(f"페이지 {current} 처리 완료 ({items}건 수집)")

    def item_collected(self, bid_id: str, title: str) -> None:
        """항목 수집 로그"""
        self.logger.debug(f"수집: [{bid_id}] {title[:50]}...")

    def item_error(self, bid_id: str, error: str) -> None:
        """항목 오류 로그"""
        self.logger.error(f"오류: [{bid_id}] {error}")

    def resuming(self, page: int, index: int) -> None:
        """재시작 로그"""
        self.logger.info(f"이전 상태에서 재시작: 페이지 {page}, 항목 {index}")

    def robots_blocked(self, url: str) -> None:
        """robots.txt 차단 로그"""
        self.logger.warning(f"robots.txt에 의해 차단됨: {url}")

    def rate_limited(self, delay: float) -> None:
        """속도 제한 로그"""
        self.logger.info(f"Crawl-delay 적용: {delay}초 대기")
