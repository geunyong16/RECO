"""
Prometheus 메트릭 모듈

크롤링 성능 및 상태를 모니터링하기 위한 Prometheus 메트릭을 제공합니다.
prometheus_client 라이브러리를 사용하여 메트릭을 수집하고 HTTP 엔드포인트로 노출합니다.
"""

import time
from contextlib import contextmanager
from typing import Callable, Optional

try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        Info,
        start_http_server,
        REGISTRY,
        CollectorRegistry,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


class CrawlerMetrics:
    """
    크롤러 Prometheus 메트릭 관리자

    수집되는 메트릭:
    - 수집된 항목 수 (성공/실패/중복)
    - 처리된 페이지 수
    - 요청 지연 시간
    - 재시도 횟수
    - 현재 크롤링 상태
    """

    def __init__(
        self,
        namespace: str = "bid_crawler",
        registry: Optional["CollectorRegistry"] = None,
    ):
        """
        Args:
            namespace: 메트릭 네임스페이스 (접두사)
            registry: Prometheus 레지스트리 (테스트용)
        """
        self.namespace = namespace
        self.enabled = PROMETHEUS_AVAILABLE
        self._server_started = False

        if not self.enabled:
            return

        self.registry = registry or REGISTRY

        # === Counter 메트릭 (누적 값) ===
        self.items_total = Counter(
            f"{namespace}_items_total",
            "Total number of items processed",
            ["status"],  # success, error, duplicate
            registry=self.registry,
        )

        self.pages_total = Counter(
            f"{namespace}_pages_total",
            "Total number of pages processed",
            registry=self.registry,
        )

        self.retries_total = Counter(
            f"{namespace}_retries_total",
            "Total number of retry attempts",
            ["reason"],  # timeout, connection_error, parse_error
            registry=self.registry,
        )

        self.errors_total = Counter(
            f"{namespace}_errors_total",
            "Total number of errors",
            ["type"],  # scrape_error, storage_error, network_error
            registry=self.registry,
        )

        # === Gauge 메트릭 (현재 값) ===
        self.current_page = Gauge(
            f"{namespace}_current_page",
            "Current page being processed",
            registry=self.registry,
        )

        self.total_pages = Gauge(
            f"{namespace}_total_pages",
            "Total number of pages to process",
            registry=self.registry,
        )

        self.items_collected = Gauge(
            f"{namespace}_items_collected",
            "Number of items collected in current run",
            registry=self.registry,
        )

        self.active_workers = Gauge(
            f"{namespace}_active_workers",
            "Number of active worker coroutines",
            registry=self.registry,
        )

        self.queue_size = Gauge(
            f"{namespace}_queue_size",
            "Current size of the task queue",
            registry=self.registry,
        )

        self.crawl_running = Gauge(
            f"{namespace}_crawl_running",
            "Whether a crawl is currently running (1=yes, 0=no)",
            registry=self.registry,
        )

        # === Histogram 메트릭 (분포) ===
        self.request_duration = Histogram(
            f"{namespace}_request_duration_seconds",
            "Time spent on HTTP requests",
            ["request_type"],  # list_page, detail_page
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
            registry=self.registry,
        )

        self.item_processing_duration = Histogram(
            f"{namespace}_item_processing_duration_seconds",
            "Time spent processing each item",
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
            registry=self.registry,
        )

        # === Info 메트릭 (메타데이터) ===
        self.crawl_info = Info(
            f"{namespace}_crawl",
            "Crawl run information",
            registry=self.registry,
        )

    def start_server(self, port: int = 8000) -> bool:
        """
        Prometheus 메트릭 서버 시작

        Args:
            port: HTTP 서버 포트

        Returns:
            서버 시작 성공 여부
        """
        if not self.enabled:
            return False

        if self._server_started:
            return True

        try:
            start_http_server(port, registry=self.registry)
            self._server_started = True
            return True
        except Exception:
            return False

    def set_crawl_info(self, run_id: str, config_summary: str = "") -> None:
        """크롤링 실행 정보 설정"""
        if not self.enabled:
            return

        self.crawl_info.info({
            "run_id": run_id,
            "config": config_summary,
        })

    def start_crawl(self) -> None:
        """크롤링 시작 표시"""
        if not self.enabled:
            return

        self.crawl_running.set(1)
        self.items_collected.set(0)
        self.current_page.set(0)
        self.total_pages.set(0)

    def end_crawl(self) -> None:
        """크롤링 종료 표시"""
        if not self.enabled:
            return

        self.crawl_running.set(0)
        self.active_workers.set(0)

    def record_item(self, status: str = "success") -> None:
        """
        항목 처리 기록

        Args:
            status: 처리 상태 ("success", "error", "duplicate")
        """
        if not self.enabled:
            return

        self.items_total.labels(status=status).inc()
        if status == "success":
            self.items_collected.inc()

    def record_page(self, page_num: int, total_pages: Optional[int] = None) -> None:
        """페이지 처리 기록"""
        if not self.enabled:
            return

        self.pages_total.inc()
        self.current_page.set(page_num)
        if total_pages:
            self.total_pages.set(total_pages)

    def record_retry(self, reason: str = "unknown") -> None:
        """재시도 기록"""
        if not self.enabled:
            return

        self.retries_total.labels(reason=reason).inc()

    def record_error(self, error_type: str = "unknown") -> None:
        """오류 기록"""
        if not self.enabled:
            return

        self.errors_total.labels(type=error_type).inc()

    def set_workers(self, count: int) -> None:
        """활성 워커 수 설정"""
        if not self.enabled:
            return

        self.active_workers.set(count)

    def set_queue_size(self, size: int) -> None:
        """큐 크기 설정"""
        if not self.enabled:
            return

        self.queue_size.set(size)

    @contextmanager
    def time_request(self, request_type: str = "detail_page"):
        """
        요청 시간 측정 컨텍스트 매니저

        Usage:
            with metrics.time_request("list_page"):
                await page.goto(url)
        """
        if not self.enabled:
            yield
            return

        start = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            self.request_duration.labels(request_type=request_type).observe(duration)

    @contextmanager
    def time_item_processing(self):
        """항목 처리 시간 측정 컨텍스트 매니저"""
        if not self.enabled:
            yield
            return

        start = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            self.item_processing_duration.observe(duration)


# 전역 메트릭 인스턴스
_metrics: Optional[CrawlerMetrics] = None


def get_metrics() -> CrawlerMetrics:
    """전역 메트릭 인스턴스 가져오기"""
    global _metrics
    if _metrics is None:
        _metrics = CrawlerMetrics()
    return _metrics


def init_metrics(
    namespace: str = "bid_crawler",
    port: Optional[int] = None,
) -> CrawlerMetrics:
    """
    메트릭 초기화

    Args:
        namespace: 메트릭 네임스페이스
        port: HTTP 서버 포트 (None이면 서버 시작 안함)

    Returns:
        초기화된 메트릭 인스턴스
    """
    global _metrics
    _metrics = CrawlerMetrics(namespace=namespace)

    if port is not None:
        _metrics.start_server(port)

    return _metrics
