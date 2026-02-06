"""
Prometheus 메트릭 모듈 단위 테스트

CrawlerMetrics 클래스의 메트릭 수집 및 서버 기능을 테스트합니다.
"""

import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock

# prometheus_client가 설치되지 않은 환경에서도 테스트 실행 가능하도록 처리
try:
    from prometheus_client import CollectorRegistry
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    CollectorRegistry = None

from bid_crawler.utils.metrics import (
    CrawlerMetrics,
    get_metrics,
    init_metrics,
    PROMETHEUS_AVAILABLE as MODULE_PROMETHEUS_AVAILABLE,
)


class TestCrawlerMetricsInitialization:
    """메트릭 초기화 테스트"""

    def test_metrics_disabled_without_prometheus(self):
        """prometheus_client 미설치 시 비활성화 확인"""
        with patch("bid_crawler.utils.metrics.PROMETHEUS_AVAILABLE", False):
            metrics = CrawlerMetrics()
            assert not metrics.enabled

    @pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not installed")
    def test_metrics_enabled_with_prometheus(self):
        """prometheus_client 설치 시 활성화 확인"""
        registry = CollectorRegistry()
        metrics = CrawlerMetrics(namespace="test", registry=registry)
        assert metrics.enabled
        assert metrics.namespace == "test"

    @pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not installed")
    def test_custom_namespace(self):
        """커스텀 네임스페이스 설정 테스트"""
        registry = CollectorRegistry()
        metrics = CrawlerMetrics(namespace="custom_crawler", registry=registry)
        assert metrics.namespace == "custom_crawler"


class TestCrawlerMetricsCounters:
    """Counter 메트릭 테스트"""

    @pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not installed")
    def test_record_item_success(self):
        """항목 수집 성공 카운터 테스트"""
        registry = CollectorRegistry()
        metrics = CrawlerMetrics(namespace="test", registry=registry)

        metrics.record_item("success")
        metrics.record_item("success")

        # Counter 값 확인
        assert metrics.items_total.labels(status="success")._value.get() == 2

    @pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not installed")
    def test_record_item_error(self):
        """항목 수집 오류 카운터 테스트"""
        registry = CollectorRegistry()
        metrics = CrawlerMetrics(namespace="test", registry=registry)

        metrics.record_item("error")

        assert metrics.items_total.labels(status="error")._value.get() == 1

    @pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not installed")
    def test_record_item_duplicate(self):
        """중복 항목 카운터 테스트"""
        registry = CollectorRegistry()
        metrics = CrawlerMetrics(namespace="test", registry=registry)

        metrics.record_item("duplicate")

        assert metrics.items_total.labels(status="duplicate")._value.get() == 1

    @pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not installed")
    def test_record_page(self):
        """페이지 처리 카운터 테스트"""
        registry = CollectorRegistry()
        metrics = CrawlerMetrics(namespace="test", registry=registry)

        metrics.record_page(1, 10)
        metrics.record_page(2, 10)

        assert metrics.pages_total._value.get() == 2

    @pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not installed")
    def test_record_retry(self):
        """재시도 카운터 테스트"""
        registry = CollectorRegistry()
        metrics = CrawlerMetrics(namespace="test", registry=registry)

        metrics.record_retry("timeout")
        metrics.record_retry("connection_error")
        metrics.record_retry("timeout")

        assert metrics.retries_total.labels(reason="timeout")._value.get() == 2
        assert metrics.retries_total.labels(reason="connection_error")._value.get() == 1

    @pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not installed")
    def test_record_error(self):
        """오류 카운터 테스트"""
        registry = CollectorRegistry()
        metrics = CrawlerMetrics(namespace="test", registry=registry)

        metrics.record_error("scrape_error")
        metrics.record_error("storage_error")

        assert metrics.errors_total.labels(type="scrape_error")._value.get() == 1
        assert metrics.errors_total.labels(type="storage_error")._value.get() == 1


class TestCrawlerMetricsGauges:
    """Gauge 메트릭 테스트"""

    @pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not installed")
    def test_current_page_gauge(self):
        """현재 페이지 게이지 테스트"""
        registry = CollectorRegistry()
        metrics = CrawlerMetrics(namespace="test", registry=registry)

        metrics.record_page(5, 20)

        assert metrics.current_page._value.get() == 5
        assert metrics.total_pages._value.get() == 20

    @pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not installed")
    def test_items_collected_gauge(self):
        """수집 항목 수 게이지 테스트"""
        registry = CollectorRegistry()
        metrics = CrawlerMetrics(namespace="test", registry=registry)

        # success 상태일 때만 items_collected 증가
        metrics.record_item("success")
        metrics.record_item("success")
        metrics.record_item("error")  # 이건 증가 안함

        assert metrics.items_collected._value.get() == 2

    @pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not installed")
    def test_set_workers(self):
        """워커 수 게이지 테스트"""
        registry = CollectorRegistry()
        metrics = CrawlerMetrics(namespace="test", registry=registry)

        metrics.set_workers(5)
        assert metrics.active_workers._value.get() == 5

        metrics.set_workers(3)
        assert metrics.active_workers._value.get() == 3

    @pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not installed")
    def test_set_queue_size(self):
        """큐 크기 게이지 테스트"""
        registry = CollectorRegistry()
        metrics = CrawlerMetrics(namespace="test", registry=registry)

        metrics.set_queue_size(10)
        assert metrics.queue_size._value.get() == 10

        metrics.set_queue_size(5)
        assert metrics.queue_size._value.get() == 5

    @pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not installed")
    def test_crawl_running_gauge(self):
        """크롤링 실행 상태 게이지 테스트"""
        registry = CollectorRegistry()
        metrics = CrawlerMetrics(namespace="test", registry=registry)

        metrics.start_crawl()
        assert metrics.crawl_running._value.get() == 1

        metrics.end_crawl()
        assert metrics.crawl_running._value.get() == 0


class TestCrawlerMetricsCrawlLifecycle:
    """크롤링 생명주기 테스트"""

    @pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not installed")
    def test_start_crawl_resets_counters(self):
        """크롤링 시작 시 카운터 초기화 테스트"""
        registry = CollectorRegistry()
        metrics = CrawlerMetrics(namespace="test", registry=registry)

        # 이전 값 설정
        metrics.items_collected.set(100)
        metrics.current_page.set(50)

        # 시작하면 초기화됨
        metrics.start_crawl()

        assert metrics.items_collected._value.get() == 0
        assert metrics.current_page._value.get() == 0
        assert metrics.crawl_running._value.get() == 1

    @pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not installed")
    def test_end_crawl_clears_workers(self):
        """크롤링 종료 시 워커 초기화 테스트"""
        registry = CollectorRegistry()
        metrics = CrawlerMetrics(namespace="test", registry=registry)

        metrics.set_workers(5)
        metrics.end_crawl()

        assert metrics.active_workers._value.get() == 0
        assert metrics.crawl_running._value.get() == 0

    @pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not installed")
    def test_set_crawl_info(self):
        """크롤링 정보 설정 테스트"""
        registry = CollectorRegistry()
        metrics = CrawlerMetrics(namespace="test", registry=registry)

        metrics.set_crawl_info("run_123", "max_pages=10, max_items=100")

        # Info 메트릭은 labels로 접근
        info_value = metrics.crawl_info._metrics[()]._value
        assert info_value["run_id"] == "run_123"
        assert info_value["config"] == "max_pages=10, max_items=100"


class TestCrawlerMetricsTimers:
    """타이머 (Histogram) 메트릭 테스트"""

    @pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not installed")
    def test_time_request_context_manager(self):
        """요청 시간 측정 컨텍스트 매니저 테스트"""
        registry = CollectorRegistry()
        metrics = CrawlerMetrics(namespace="test", registry=registry)

        with metrics.time_request("list_page"):
            pass  # 즉시 완료

        # Histogram에 샘플이 기록되었는지 확인
        assert metrics.request_duration.labels(request_type="list_page")._count.get() == 1

    @pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not installed")
    def test_time_item_processing_context_manager(self):
        """항목 처리 시간 측정 컨텍스트 매니저 테스트"""
        registry = CollectorRegistry()
        metrics = CrawlerMetrics(namespace="test", registry=registry)

        with metrics.time_item_processing():
            pass

        assert metrics.item_processing_duration._count.get() == 1


class TestCrawlerMetricsServer:
    """메트릭 서버 테스트"""

    @pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not installed")
    def test_start_server_success(self):
        """서버 시작 성공 테스트"""
        registry = CollectorRegistry()
        metrics = CrawlerMetrics(namespace="test", registry=registry)

        with patch("bid_crawler.utils.metrics.start_http_server") as mock_start:
            result = metrics.start_server(port=9999)

            assert result is True
            mock_start.assert_called_once_with(9999, registry=registry)

    @pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not installed")
    def test_start_server_failure(self):
        """서버 시작 실패 테스트 (포트 충돌 등)"""
        registry = CollectorRegistry()
        metrics = CrawlerMetrics(namespace="test", registry=registry)

        with patch("bid_crawler.utils.metrics.start_http_server") as mock_start:
            mock_start.side_effect = OSError("Address already in use")
            result = metrics.start_server(port=8000)

            assert result is False

    @pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not installed")
    def test_start_server_already_started(self):
        """서버 중복 시작 방지 테스트"""
        registry = CollectorRegistry()
        metrics = CrawlerMetrics(namespace="test", registry=registry)

        with patch("bid_crawler.utils.metrics.start_http_server") as mock_start:
            metrics.start_server(port=9999)
            metrics.start_server(port=9999)  # 두 번째 호출

            # 한 번만 호출되어야 함
            assert mock_start.call_count == 1

    def test_start_server_disabled(self):
        """Prometheus 비활성화 시 서버 시작 안함"""
        with patch("bid_crawler.utils.metrics.PROMETHEUS_AVAILABLE", False):
            metrics = CrawlerMetrics()
            result = metrics.start_server(port=8000)

            assert result is False


class TestCrawlerMetricsDisabled:
    """Prometheus 비활성화 시 동작 테스트"""

    def test_record_item_when_disabled(self):
        """비활성화 시 record_item 호출해도 오류 없음"""
        with patch("bid_crawler.utils.metrics.PROMETHEUS_AVAILABLE", False):
            metrics = CrawlerMetrics()
            # 예외 발생하지 않아야 함
            metrics.record_item("success")
            metrics.record_item("error")

    def test_record_page_when_disabled(self):
        """비활성화 시 record_page 호출해도 오류 없음"""
        with patch("bid_crawler.utils.metrics.PROMETHEUS_AVAILABLE", False):
            metrics = CrawlerMetrics()
            metrics.record_page(1, 10)

    def test_time_request_when_disabled(self):
        """비활성화 시 time_request 컨텍스트 매니저 정상 동작"""
        with patch("bid_crawler.utils.metrics.PROMETHEUS_AVAILABLE", False):
            metrics = CrawlerMetrics()
            with metrics.time_request("test"):
                pass  # 예외 발생하지 않아야 함

    def test_time_item_processing_when_disabled(self):
        """비활성화 시 time_item_processing 컨텍스트 매니저 정상 동작"""
        with patch("bid_crawler.utils.metrics.PROMETHEUS_AVAILABLE", False):
            metrics = CrawlerMetrics()
            with metrics.time_item_processing():
                pass


class TestMetricsModuleFunctions:
    """모듈 레벨 함수 테스트"""

    def test_get_metrics_returns_singleton(self):
        """get_metrics가 싱글톤 반환하는지 테스트"""
        # 모듈 전역 변수 초기화
        import bid_crawler.utils.metrics as metrics_module
        metrics_module._metrics = None

        metrics1 = get_metrics()
        metrics2 = get_metrics()

        assert metrics1 is metrics2

    @pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not installed")
    def test_init_metrics_with_port(self):
        """init_metrics로 서버 시작 테스트"""
        import bid_crawler.utils.metrics as metrics_module
        metrics_module._metrics = None

        with patch("bid_crawler.utils.metrics.start_http_server"):
            metrics = init_metrics(namespace="test_init", port=9999)

            assert metrics.namespace == "test_init"

    def test_init_metrics_without_port(self):
        """init_metrics 포트 없이 호출 테스트"""
        import bid_crawler.utils.metrics as metrics_module
        metrics_module._metrics = None

        metrics = init_metrics(namespace="test_no_port")

        assert metrics is not None
        assert not metrics._server_started
