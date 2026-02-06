"""
크롤러 설정 관리 모듈

환경 변수, 설정 파일, CLI 옵션을 통합 관리합니다.
python-dotenv를 통한 .env 파일 지원을 포함합니다.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator


class BrowserConfig(BaseModel):
    """브라우저 설정"""

    headless: bool = Field(default=True, description="헤드리스 모드 실행 여부")
    timeout: int = Field(default=30000, description="페이지 로드 타임아웃 (ms)")
    slow_mo: int = Field(default=100, description="작업 간 딜레이 (ms)")
    viewport_width: int = Field(default=1920, description="뷰포트 너비")
    viewport_height: int = Field(default=1080, description="뷰포트 높이")
    user_agent: Optional[str] = Field(
        default="BidCrawler/1.0 (+https://github.com/yourusername/bid-crawler)",
        description="User-Agent 문자열",
    )


class RetryConfig(BaseModel):
    """재시도 설정"""

    max_retries: int = Field(default=3, description="최대 재시도 횟수")
    retry_delay: float = Field(default=2.0, description="재시도 간 대기 시간 (초)")
    exponential_backoff: bool = Field(default=True, description="지수 백오프 적용 여부")
    max_delay: float = Field(default=60.0, description="최대 대기 시간 (초)")
    jitter: bool = Field(default=True, description="지터(랜덤 지연) 적용 여부")


class StorageConfig(BaseModel):
    """저장소 설정"""

    data_dir: Path = Field(default=Path("data"), description="데이터 저장 디렉토리")
    state_file: Path = Field(
        default=Path("data/crawl_state.json"), description="상태 파일 경로"
    )
    output_format: Literal["json", "csv", "both"] = Field(
        default="json", description="출력 형식"
    )
    save_interval: int = Field(default=10, description="저장 간격 (수집 건수)")


class SchedulerConfig(BaseModel):
    """스케줄러 설정"""

    enabled: bool = Field(default=False, description="스케줄러 활성화 여부")
    mode: Literal["interval", "cron"] = Field(default="interval", description="실행 모드")
    interval_minutes: int = Field(default=60, description="interval 모드: 실행 간격 (분)")
    cron_expression: str = Field(
        default="0 */6 * * *", description="cron 모드: cron 표현식"
    )

    @model_validator(mode="after")
    def validate_cron_expression(self) -> "SchedulerConfig":
        """cron 표현식 유효성 검사"""
        if self.mode == "cron":
            parts = self.cron_expression.split()
            if len(parts) < 5:
                raise ValueError(
                    f"Invalid cron expression: {self.cron_expression}. "
                    "Expected format: 'minute hour day month weekday'"
                )
        return self


class LoggingConfig(BaseModel):
    """로깅 설정"""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="로그 레벨"
    )
    file: Optional[Path] = Field(
        default=Path("logs/crawler.log"), description="로그 파일 경로"
    )
    rotation: Literal["size", "time", "none"] = Field(
        default="size", description="로그 회전 방식"
    )
    max_bytes: int = Field(default=10 * 1024 * 1024, description="회전 시 최대 파일 크기")
    backup_count: int = Field(default=5, description="보관할 백업 파일 수")


class RobotsConfig(BaseModel):
    """robots.txt 설정"""

    enabled: bool = Field(default=True, description="robots.txt 확인 활성화")
    respect_crawl_delay: bool = Field(default=True, description="Crawl-delay 준수 여부")


class ConcurrencyConfig(BaseModel):
    """동시성 처리 설정"""

    max_workers: int = Field(default=3, description="동시 처리 워커 수", ge=1, le=10)
    queue_size: int = Field(default=50, description="작업 큐 최대 크기")
    batch_delay: float = Field(default=0.5, description="배치 처리 간 딜레이 (초)")


class MonitoringConfig(BaseModel):
    """
    모니터링 설정

    Prometheus 메트릭 및 구조화된 로깅(ELK 스택)을 위한 설정입니다.
    """

    # Prometheus 설정
    prometheus_enabled: bool = Field(
        default=False, description="Prometheus 메트릭 활성화"
    )
    prometheus_port: int = Field(
        default=8000, description="Prometheus 메트릭 서버 포트", ge=1024, le=65535
    )
    metrics_namespace: str = Field(
        default="bid_crawler", description="메트릭 네임스페이스 (접두사)"
    )

    # 구조화된 로깅 (ELK 스택 통합)
    json_logging: bool = Field(
        default=False, description="JSON 형식 로깅 활성화 (ELK 스택 통합용)"
    )
    log_extra_fields: Optional[dict[str, str]] = Field(
        default=None,
        description="로그에 추가할 필드 (예: {'service': 'bid_crawler', 'env': 'prod'})",
    )


class CrawlerConfig(BaseModel):
    """
    크롤러 통합 설정

    모든 설정을 하나의 객체로 관리합니다.
    환경 변수, 설정 파일, CLI 옵션 순서로 우선순위가 적용됩니다.
    """

    # 크롤링 대상 설정
    base_url: str = Field(default="https://www.g2b.go.kr", description="나라장터 기본 URL")
    bid_list_url: str = Field(
        default="https://www.g2b.go.kr/pt/menu/selectSubFrame.do?framesrc=/pt/menu/frameTgong.do",
        description="입찰공고 목록 페이지 URL",
    )

    # 크롤링 범위 설정
    max_pages: Optional[int] = Field(
        default=None, description="최대 크롤링 페이지 수 (None: 무제한)"
    )
    max_items: Optional[int] = Field(
        default=None, description="최대 수집 항목 수 (None: 무제한)"
    )

    # 필터 설정
    keyword: Optional[str] = Field(default=None, description="검색 키워드")
    bid_type: Optional[str] = Field(
        default=None, description="입찰 유형 필터 (물품, 용역, 공사 등)"
    )

    # 하위 설정
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    robots: RobotsConfig = Field(default_factory=RobotsConfig)
    concurrency: ConcurrencyConfig = Field(default_factory=ConcurrencyConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)

    # 실행 ID (자동 생성)
    run_id: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"),
        description="실행 식별자",
    )

    # 선택자 설정 파일 경로
    selectors_file: Optional[Path] = Field(
        default=Path("config/selectors.yaml"), description="선택자 설정 파일 경로"
    )

    # 레거시 호환성을 위한 속성
    @property
    def log_level(self) -> str:
        """로그 레벨 (레거시 호환)"""
        return self.logging.level

    @property
    def log_file(self) -> Optional[Path]:
        """로그 파일 (레거시 호환)"""
        return self.logging.file

    @classmethod
    def from_env(cls, env_file: Optional[Path] = None) -> "CrawlerConfig":
        """
        환경 변수에서 설정 로드

        Args:
            env_file: .env 파일 경로 (None이면 자동 탐색)

        Returns:
            CrawlerConfig 인스턴스
        """
        # .env 파일 로드
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()  # 현재 디렉토리 및 상위 디렉토리에서 자동 탐색

        return cls(
            base_url=os.getenv("CRAWLER_BASE_URL", cls.model_fields["base_url"].default),
            max_pages=(
                int(os.getenv("CRAWLER_MAX_PAGES"))
                if os.getenv("CRAWLER_MAX_PAGES")
                else None
            ),
            max_items=(
                int(os.getenv("CRAWLER_MAX_ITEMS"))
                if os.getenv("CRAWLER_MAX_ITEMS")
                else None
            ),
            keyword=os.getenv("CRAWLER_KEYWORD"),
            browser=BrowserConfig(
                headless=os.getenv("CRAWLER_HEADLESS", "true").lower() == "true",
                timeout=int(os.getenv("CRAWLER_TIMEOUT", "30000")),
            ),
            logging=LoggingConfig(
                level=os.getenv("CRAWLER_LOG_LEVEL", "INFO"),  # type: ignore
            ),
            storage=StorageConfig(
                data_dir=Path(os.getenv("CRAWLER_DATA_DIR", "data")),
                output_format=os.getenv("CRAWLER_OUTPUT_FORMAT", "json"),  # type: ignore
            ),
            scheduler=SchedulerConfig(
                enabled=os.getenv("CRAWLER_SCHEDULER_ENABLED", "false").lower() == "true",
                mode=os.getenv("CRAWLER_SCHEDULER_MODE", "interval"),  # type: ignore
                interval_minutes=int(os.getenv("CRAWLER_SCHEDULER_INTERVAL", "60")),
                cron_expression=os.getenv("CRAWLER_SCHEDULER_CRON", "0 */6 * * *"),
            ),
            robots=RobotsConfig(
                enabled=os.getenv("CRAWLER_ROBOTS_ENABLED", "true").lower() == "true",
            ),
        )

    @classmethod
    def from_yaml(cls, config_file: Path) -> "CrawlerConfig":
        """
        YAML 설정 파일에서 로드

        Args:
            config_file: 설정 파일 경로

        Returns:
            CrawlerConfig 인스턴스
        """
        with open(config_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return cls(**data)

    def ensure_directories(self) -> None:
        """필요한 디렉토리 생성"""
        self.storage.data_dir.mkdir(parents=True, exist_ok=True)
        if self.logging.file:
            self.logging.file.parent.mkdir(parents=True, exist_ok=True)

    def load_selectors(self) -> dict[str, Any]:
        """
        선택자 설정 파일 로드

        Returns:
            선택자 설정 딕셔너리
        """
        if self.selectors_file and self.selectors_file.exists():
            with open(self.selectors_file, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {}

    def to_summary(self) -> str:
        """설정 요약 문자열 생성"""
        parts = [
            f"URL={self.base_url}",
            f"max_pages={self.max_pages or 'unlimited'}",
            f"max_items={self.max_items or 'unlimited'}",
        ]
        if self.keyword:
            parts.append(f"keyword={self.keyword}")
        return ", ".join(parts)
