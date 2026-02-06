"""
config.py 단위 테스트

CrawlerConfig 및 하위 설정 클래스들을 테스트합니다.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from bid_crawler.config import (
    BrowserConfig,
    CrawlerConfig,
    LoggingConfig,
    RetryConfig,
    RobotsConfig,
    SchedulerConfig,
    StorageConfig,
)


class TestBrowserConfig:
    """BrowserConfig 테스트"""

    def test_default_values(self) -> None:
        """기본값 테스트"""
        config = BrowserConfig()
        assert config.headless is True
        assert config.timeout == 30000
        assert config.slow_mo == 100
        assert config.viewport_width == 1920
        assert config.viewport_height == 1080
        assert config.user_agent is not None

    def test_custom_values(self) -> None:
        """사용자 정의 값 테스트"""
        config = BrowserConfig(
            headless=False,
            timeout=60000,
            slow_mo=200,
            viewport_width=1280,
            viewport_height=720,
        )
        assert config.headless is False
        assert config.timeout == 60000
        assert config.slow_mo == 200


class TestRetryConfig:
    """RetryConfig 테스트"""

    def test_default_values(self) -> None:
        """기본값 테스트"""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.retry_delay == 2.0
        assert config.exponential_backoff is True
        assert config.max_delay == 60.0
        assert config.jitter is True

    def test_custom_values(self) -> None:
        """사용자 정의 값 테스트"""
        config = RetryConfig(
            max_retries=5,
            retry_delay=1.0,
            exponential_backoff=False,
            jitter=False,
        )
        assert config.max_retries == 5
        assert config.exponential_backoff is False


class TestStorageConfig:
    """StorageConfig 테스트"""

    def test_default_values(self) -> None:
        """기본값 테스트"""
        config = StorageConfig()
        assert config.data_dir == Path("data")
        assert config.output_format == "json"
        assert config.save_interval == 10

    def test_output_format_validation(self) -> None:
        """출력 형식 유효성 검사"""
        # 유효한 형식
        for fmt in ["json", "csv", "both"]:
            config = StorageConfig(output_format=fmt)  # type: ignore
            assert config.output_format == fmt

        # 유효하지 않은 형식
        with pytest.raises(ValueError):
            StorageConfig(output_format="xml")  # type: ignore


class TestSchedulerConfig:
    """SchedulerConfig 테스트"""

    def test_default_values(self) -> None:
        """기본값 테스트"""
        config = SchedulerConfig()
        assert config.enabled is False
        assert config.mode == "interval"
        assert config.interval_minutes == 60

    def test_valid_cron_expression(self) -> None:
        """유효한 cron 표현식 테스트"""
        config = SchedulerConfig(
            mode="cron",
            cron_expression="0 9 * * *",
        )
        assert config.cron_expression == "0 9 * * *"

    def test_invalid_cron_expression(self) -> None:
        """유효하지 않은 cron 표현식 테스트"""
        with pytest.raises(ValueError, match="Invalid cron expression"):
            SchedulerConfig(
                mode="cron",
                cron_expression="0 9 *",  # 5개 필드 필요
            )


class TestLoggingConfig:
    """LoggingConfig 테스트"""

    def test_default_values(self) -> None:
        """기본값 테스트"""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert config.rotation == "size"
        assert config.max_bytes == 10 * 1024 * 1024
        assert config.backup_count == 5

    def test_log_level_validation(self) -> None:
        """로그 레벨 유효성 검사"""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            config = LoggingConfig(level=level)  # type: ignore
            assert config.level == level


class TestRobotsConfig:
    """RobotsConfig 테스트"""

    def test_default_values(self) -> None:
        """기본값 테스트"""
        config = RobotsConfig()
        assert config.enabled is True
        assert config.respect_crawl_delay is True

    def test_disabled(self) -> None:
        """비활성화 테스트"""
        config = RobotsConfig(enabled=False)
        assert config.enabled is False


class TestCrawlerConfig:
    """CrawlerConfig 테스트"""

    def test_default_values(self) -> None:
        """기본값 테스트"""
        config = CrawlerConfig()
        assert "g2b.go.kr" in config.base_url
        assert config.max_pages is None
        assert config.max_items is None
        assert config.keyword is None

    def test_nested_configs(self) -> None:
        """중첩 설정 테스트"""
        config = CrawlerConfig()
        assert isinstance(config.browser, BrowserConfig)
        assert isinstance(config.retry, RetryConfig)
        assert isinstance(config.storage, StorageConfig)
        assert isinstance(config.scheduler, SchedulerConfig)
        assert isinstance(config.logging, LoggingConfig)
        assert isinstance(config.robots, RobotsConfig)

    def test_legacy_properties(self) -> None:
        """레거시 호환성 속성 테스트"""
        config = CrawlerConfig()
        assert config.log_level == config.logging.level
        assert config.log_file == config.logging.file

    def test_run_id_auto_generation(self) -> None:
        """실행 ID 자동 생성 테스트"""
        config = CrawlerConfig()
        assert config.run_id is not None
        assert len(config.run_id) == 15  # YYYYMMDD_HHMMSS

    def test_to_summary(self) -> None:
        """요약 문자열 생성 테스트"""
        config = CrawlerConfig(max_pages=10, keyword="테스트")
        summary = config.to_summary()
        assert "max_pages=10" in summary
        assert "keyword=테스트" in summary

    def test_ensure_directories(self) -> None:
        """디렉토리 생성 테스트"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = CrawlerConfig(
                storage=StorageConfig(data_dir=Path(tmpdir) / "data"),
                logging=LoggingConfig(file=Path(tmpdir) / "logs" / "test.log"),
            )
            config.ensure_directories()
            assert (Path(tmpdir) / "data").exists()
            assert (Path(tmpdir) / "logs").exists()

    def test_from_env(self) -> None:
        """환경 변수에서 로드 테스트"""
        env_vars = {
            "CRAWLER_BASE_URL": "https://example.com",
            "CRAWLER_MAX_PAGES": "5",
            "CRAWLER_MAX_ITEMS": "100",
            "CRAWLER_KEYWORD": "테스트",
            "CRAWLER_HEADLESS": "false",
            "CRAWLER_LOG_LEVEL": "DEBUG",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            config = CrawlerConfig.from_env()
            assert config.base_url == "https://example.com"
            assert config.max_pages == 5
            assert config.max_items == 100
            assert config.keyword == "테스트"
            assert config.browser.headless is False
            assert config.logging.level == "DEBUG"

    def test_from_yaml(self) -> None:
        """YAML 파일에서 로드 테스트"""
        yaml_content = {
            "base_url": "https://test.example.com",
            "max_pages": 3,
            "browser": {
                "headless": False,
                "timeout": 60000,
            },
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            yaml.dump(yaml_content, f)
            f.flush()

            config = CrawlerConfig.from_yaml(Path(f.name))
            assert config.base_url == "https://test.example.com"
            assert config.max_pages == 3
            assert config.browser.headless is False
            assert config.browser.timeout == 60000

            os.unlink(f.name)

    def test_load_selectors(self) -> None:
        """선택자 설정 로드 테스트"""
        selectors_content = {
            "list_page": {
                "table": "table.list",
                "rows": "table tbody tr",
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            selectors_file = Path(tmpdir) / "selectors.yaml"
            with open(selectors_file, "w", encoding="utf-8") as f:
                yaml.dump(selectors_content, f)

            config = CrawlerConfig(selectors_file=selectors_file)
            selectors = config.load_selectors()
            assert selectors["list_page"]["table"] == "table.list"

    def test_load_selectors_missing_file(self) -> None:
        """선택자 설정 파일 없을 때 테스트"""
        config = CrawlerConfig(selectors_file=Path("/nonexistent/selectors.yaml"))
        selectors = config.load_selectors()
        assert selectors == {}
