"""
메인 크롤러 오케스트레이터

모든 컴포넌트를 조합하여 크롤링 워크플로우를 실행합니다.
Producer-Consumer 패턴으로 구현되어 관심사가 분리되어 있습니다.
"""

import asyncio
from typing import Optional, Callable, AsyncIterator, Protocol
from datetime import datetime
from dataclasses import dataclass

from bid_crawler.config import CrawlerConfig
from bid_crawler.models.bid_notice import BidNotice, BidNoticeDetail
from bid_crawler.models.crawl_state import CrawlState
from bid_crawler.scrapers.list_scraper import ListScraper
from bid_crawler.scrapers.detail_scraper import DetailScraper
from bid_crawler.storage.state_manager import StateManager
from bid_crawler.storage.json_storage import JsonStorage
from bid_crawler.storage.csv_storage import CsvStorage
from bid_crawler.utils.browser import BrowserManager
from bid_crawler.utils.retry import retry_async, RetryError
from bid_crawler.utils.logger import setup_logger, get_logger, CrawlLogger
from bid_crawler.utils.metrics import CrawlerMetrics, get_metrics, init_metrics

logger = get_logger(__name__)


# === Data Classes ===

@dataclass
class CrawlTask:
    """
    크롤링 작업 단위

    Producer가 생성하고 Consumer가 처리하는 작업 단위입니다.

    Attributes:
        notice: 목록에서 추출한 입찰공고 정보
        page_num: 해당 항목이 있는 페이지 번호
        index: 페이지 내 인덱스
    """
    notice: BidNotice
    page_num: int
    index: int


# === Repository Protocol (for DI) ===

class BidRepositoryProtocol(Protocol):
    """
    BidRepository 프로토콜

    의존성 주입을 위한 프로토콜입니다.
    JsonStorage 등이 이 프로토콜을 만족합니다.
    """
    def save(self, bid) -> bool: ...
    def exists(self, bid_id: str) -> bool: ...
    def flush(self) -> bool: ...
    def close(self) -> None: ...


# === Producer: Page Navigator ===

class PageNavigator:
    """
    페이지 네비게이션 담당 (Producer)

    목록 페이지를 순회하며 크롤링 작업을 생성합니다.
    AsyncIterator 패턴을 사용하여 메모리 효율적으로 작업을 생성합니다.
    """

    def __init__(
        self,
        list_scraper: ListScraper,
        config: CrawlerConfig,
        state_manager: StateManager,
    ):
        """
        Args:
            list_scraper: 목록 페이지 스크래퍼
            config: 크롤러 설정
            state_manager: 상태 관리자
        """
        self.list_scraper = list_scraper
        self.config = config
        self.state_manager = state_manager
        self.logger = get_logger("PageNavigator")

    async def produce_tasks(
        self,
        start_page: int = 1,
        start_index: int = 0,
    ) -> AsyncIterator[CrawlTask]:
        """
        크롤링 작업 생성 (Generator 패턴)

        페이지를 순회하며 각 항목을 CrawlTask로 yield합니다.

        Args:
            start_page: 시작 페이지 번호
            start_index: 시작 페이지 내 인덱스

        Yields:
            CrawlTask: 개별 크롤링 작업
        """
        current_page = start_page

        while True:
            # 최대 페이지 확인
            if self.config.max_pages and current_page > self.config.max_pages:
                self.logger.info(f"Max pages reached: {self.config.max_pages}")
                break

            self.logger.info(f"Processing page {current_page}")
            self.state_manager.update_progress(page=current_page)

            # 목록 스크래핑
            try:
                bid_list = await retry_async(
                    self.list_scraper.scrape,
                    max_retries=self.config.retry.max_retries,
                    base_delay=self.config.retry.retry_delay,
                    on_retry=lambda a, e: self.state_manager.record_retry(),
                )
            except RetryError as e:
                self.logger.error(f"Page {current_page} scraping failed: {e}")
                self.state_manager.record_error(str(e))
                break

            if not bid_list.items:
                self.logger.info("No more items")
                break

            # 전체 페이지 수 업데이트
            self.state_manager.update_progress(total_pages=bid_list.total_pages)

            # 각 항목을 Task로 yield
            idx_start = start_index if current_page == start_page else 0
            for idx, notice in enumerate(bid_list.items[idx_start:], start=idx_start):
                yield CrawlTask(notice=notice, page_num=current_page, index=idx)

            # 페이지 완료
            self.state_manager.complete_page(current_page)

            # 다음 페이지 이동
            if not bid_list.has_next:
                self.logger.info("Last page reached")
                break

            if not await self.list_scraper.go_to_next_page():
                self.logger.warning("Failed to navigate to next page")
                break

            current_page += 1
            await asyncio.sleep(1)  # 페이지 간 딜레이


# === Consumer: Item Processor ===

class ItemProcessor:
    """
    항목 처리 담당 (Consumer)

    상세 페이지 크롤링과 데이터 저장을 담당합니다.
    """

    def __init__(
        self,
        detail_scraper: DetailScraper,
        repository: BidRepositoryProtocol,
        config: CrawlerConfig,
        state_manager: StateManager,
        crawl_logger: CrawlLogger,
    ):
        """
        Args:
            detail_scraper: 상세 페이지 스크래퍼
            repository: 저장소 (BidRepository 인터페이스)
            config: 크롤러 설정
            state_manager: 상태 관리자
            crawl_logger: 크롤링 로거
        """
        self.detail_scraper = detail_scraper
        self.repository = repository
        self.config = config
        self.state_manager = state_manager
        self.crawl_logger = crawl_logger
        self.logger = get_logger("ItemProcessor")

    async def process(self, task: CrawlTask, page) -> Optional[BidNoticeDetail]:
        """
        단일 작업 처리

        Args:
            task: 크롤링 작업
            page: Playwright 페이지

        Returns:
            처리된 상세 정보 또는 None
        """
        notice = task.notice

        # 중복 확인
        if self.state_manager.is_collected(notice.bid_notice_id):
            self.logger.debug(f"Skipping duplicate: {notice.bid_notice_id}")
            return None

        # 진행 상태 업데이트
        self.state_manager.update_progress(index=task.index)

        # 상세 크롤링
        detail = await self._crawl_detail(notice, page)

        if detail:
            # 저장
            self.repository.save(detail)
            self.state_manager.mark_collected(notice.bid_notice_id)

            self.crawl_logger.item_collected(
                detail.bid_notice_id, detail.title
            )

        return detail

    async def _crawl_detail(
        self,
        notice: BidNotice,
        page,
    ) -> Optional[BidNoticeDetail]:
        """
        상세 페이지 크롤링

        Args:
            notice: 목록에서 가져온 공고 정보
            page: Playwright 페이지

        Returns:
            상세 정보 또는 None
        """
        if not notice.detail_url:
            return BidNoticeDetail(
                **notice.model_dump(),
                detail_crawled_at=datetime.now(),
                crawl_success=False,
                crawl_error="No detail URL",
            )

        try:
            # URL 정규화
            detail_url = notice.detail_url
            if not detail_url.startswith("http"):
                detail_url = f"{self.config.base_url}{detail_url}"

            detail = await retry_async(
                self.detail_scraper.scrape_from_url,
                detail_url,
                notice,
                max_retries=self.config.retry.max_retries,
                base_delay=self.config.retry.retry_delay,
                on_retry=lambda a, e: self.state_manager.record_retry(),
            )

            # 목록으로 복귀
            await page.go_back()
            await asyncio.sleep(0.5)

            return detail

        except RetryError as e:
            self.logger.warning(f"Detail crawl failed ({notice.bid_notice_id}): {e}")
            self.state_manager.record_error(
                str(e),
                {"bid_id": notice.bid_notice_id, "url": notice.detail_url},
            )
            self.crawl_logger.item_error(notice.bid_notice_id, str(e))

            return BidNoticeDetail(
                **notice.model_dump(),
                detail_crawled_at=datetime.now(),
                crawl_success=False,
                crawl_error=str(e),
            )

        except Exception as e:
            self.logger.error(f"Unexpected error ({notice.bid_notice_id}): {e}")
            return None


# === Orchestrator: Bid Crawler ===

class BidCrawler:
    """
    입찰공고 크롤러 (Orchestrator)

    Producer-Consumer 패턴으로 구성됩니다:
    - PageNavigator: 페이지 순회 및 작업 생성 (Producer)
    - ItemProcessor: 항목 처리 및 저장 (Consumer)

    의존성 주입(DI)을 지원하여 테스트 용이성을 높였습니다.
    """

    def __init__(
        self,
        config: Optional[CrawlerConfig] = None,
        repository: Optional[BidRepositoryProtocol] = None,
    ):
        """
        Args:
            config: 크롤러 설정 (None이면 기본값 사용)
            repository: 저장소 인스턴스 (None이면 JsonStorage 사용, DI 지원)
        """
        self.config = config or CrawlerConfig()
        self.config.ensure_directories()

        # 로거 설정 (JSON 형식 로깅 지원)
        setup_logger(
            "bid_crawler",
            level=self.config.log_level,
            log_file=self.config.log_file,
            json_format=self.config.monitoring.json_logging,
            extra_fields=self.config.monitoring.log_extra_fields,
        )
        self.crawl_logger = CrawlLogger()

        # Prometheus 메트릭 초기화
        self.metrics: CrawlerMetrics = init_metrics(
            namespace=self.config.monitoring.metrics_namespace,
            port=self.config.monitoring.prometheus_port if self.config.monitoring.prometheus_enabled else None,
        )

        # 컴포넌트 초기화
        self.browser_manager = BrowserManager(self.config.browser)
        self.state_manager = StateManager(self.config.storage.state_file)

        # Repository 주입 또는 기본 생성 (DIP 적용)
        self._injected_repository = repository
        self.json_storage = repository or JsonStorage(
            self.config.storage.data_dir,
            filename=f"bid_notices_{self.config.run_id}.json",
        )

        # CSV 저장소 (선택적)
        self.csv_storage = CsvStorage(
            self.config.storage.data_dir,
            filename=f"bid_notices_{self.config.run_id}.csv",
        ) if self.config.storage.output_format in ["csv", "both"] else None

        # 콜백
        self._on_item_collected: Optional[Callable[[BidNoticeDetail], None]] = None
        self._on_page_completed: Optional[Callable[[int, int], None]] = None

    def on_item_collected(self, callback: Callable[[BidNoticeDetail], None]) -> None:
        """항목 수집 시 콜백 등록"""
        self._on_item_collected = callback

    def on_page_completed(self, callback: Callable[[int, int], None]) -> None:
        """페이지 완료 시 콜백 등록"""
        self._on_page_completed = callback

    async def run(self, resume: bool = True) -> CrawlState:
        """
        크롤링 실행

        Args:
            resume: True면 이전 상태에서 재시작

        Returns:
            최종 크롤링 상태
        """
        # 상태 초기화
        state = self.state_manager.initialize(self.config.run_id, resume=resume)

        self.crawl_logger.start_crawl(
            self.config.run_id,
            f"max_pages={self.config.max_pages}, max_items={self.config.max_items}"
        )

        # 메트릭 시작
        self.metrics.set_crawl_info(
            self.config.run_id,
            self.config.to_summary(),
        )
        self.metrics.start_crawl()

        try:
            async with self.browser_manager:
                await self._execute_crawl_pipeline(state)

        except KeyboardInterrupt:
            logger.warning("Interrupted by user")
            self.state_manager.save(force=True)
            self.metrics.record_error("interrupted")

        except Exception as e:
            logger.error(f"Crawl error: {e}")
            self.state_manager.record_error(str(e))
            self.state_manager.save(force=True)
            self.metrics.record_error("crawl_error")
            raise

        finally:
            # 메트릭 종료
            self.metrics.end_crawl()

            # 저장소 종료
            self.json_storage.close()
            if self.csv_storage:
                self.csv_storage.close()

            # 통계 출력
            self._log_statistics()

        return self.state_manager.state

    async def _execute_crawl_pipeline(self, state: CrawlState) -> None:
        """
        Producer-Consumer 파이프라인 실행 (동시성 처리 지원)

        Args:
            state: 크롤링 상태
        """
        async with self.browser_manager.get_page() as page:
            # 목록 페이지 이동
            logger.info(f"Navigating to list page: {self.config.bid_list_url}")
            await page.goto(self.config.bid_list_url, wait_until="networkidle")
            await asyncio.sleep(2)

            # 스크래퍼 초기화
            list_scraper = ListScraper(page)
            detail_scraper = DetailScraper(page)

            # Producer/Consumer 초기화
            navigator = PageNavigator(list_scraper, self.config, self.state_manager)
            processor = ItemProcessor(
                detail_scraper,
                self.json_storage,
                self.config,
                self.state_manager,
                self.crawl_logger,
            )

            # 재시작 지점
            start_page, start_index = self.state_manager.get_resume_point()
            if start_page > 1:
                self.crawl_logger.resuming(start_page, start_index)
                await list_scraper.go_to_page(start_page)

            # 동시성 처리 설정
            max_workers = self.config.concurrency.max_workers
            queue_size = self.config.concurrency.queue_size
            batch_delay = self.config.concurrency.batch_delay

            # 작업 큐 및 세마포어
            task_queue: asyncio.Queue[Optional[CrawlTask]] = asyncio.Queue(maxsize=queue_size)
            semaphore = asyncio.Semaphore(max_workers)
            items_collected = 0
            items_lock = asyncio.Lock()
            current_page = start_page
            page_items = 0

            async def worker(worker_id: int) -> None:
                """동시성 워커"""
                nonlocal items_collected, current_page, page_items

                while True:
                    task = await task_queue.get()

                    # 종료 신호
                    if task is None:
                        task_queue.task_done()
                        break

                    try:
                        async with semaphore:
                            # 최대 항목 수 확인
                            async with items_lock:
                                if self.config.max_items and items_collected >= self.config.max_items:
                                    task_queue.task_done()
                                    continue

                            # 페이지 변경 감지 및 콜백
                            async with items_lock:
                                if task.page_num != current_page:
                                    self.crawl_logger.page_progress(
                                        current_page,
                                        self.state_manager.state.progress.total_pages,
                                        page_items,
                                    )
                                    # 페이지 메트릭 기록
                                    self.metrics.record_page(
                                        current_page,
                                        self.state_manager.state.progress.total_pages,
                                    )
                                    if self._on_page_completed:
                                        self._on_page_completed(
                                            current_page,
                                            self.state_manager.state.progress.total_pages,
                                        )
                                    current_page = task.page_num
                                    page_items = 0

                            # 항목 처리 (Consumer) - 처리 시간 측정
                            with self.metrics.time_item_processing():
                                detail = await processor.process(task, page)

                            if detail:
                                async with items_lock:
                                    items_collected += 1
                                    page_items += 1

                                # 메트릭 기록
                                self.metrics.record_item("success")

                                # CSV 저장
                                if self.csv_storage and self.config.storage.output_format in ["csv", "both"]:
                                    self.csv_storage.save(detail)

                                # 항목 수집 콜백
                                if self._on_item_collected:
                                    self._on_item_collected(detail)

                                # 저장 간격
                                async with items_lock:
                                    if items_collected % self.config.storage.save_interval == 0:
                                        self.json_storage.flush()
                                        self.state_manager.save()

                            # 배치 처리 딜레이
                            await asyncio.sleep(batch_delay)

                    except Exception as e:
                        logger.error(f"Worker {worker_id} error: {e}")
                        self.metrics.record_item("error")

                    finally:
                        task_queue.task_done()

            # 워커 시작
            workers = [asyncio.create_task(worker(i)) for i in range(max_workers)]
            logger.info(f"Started {max_workers} concurrent workers")
            self.metrics.set_workers(max_workers)

            # Producer: 작업 큐에 추가
            try:
                async for task in navigator.produce_tasks(start_page, start_index):
                    # 최대 항목 수 확인
                    async with items_lock:
                        if self.config.max_items and items_collected >= self.config.max_items:
                            logger.info(f"Max items reached: {self.config.max_items}")
                            break

                    await task_queue.put(task)
                    self.metrics.set_queue_size(task_queue.qsize())

            finally:
                # 종료 신호 전송
                for _ in range(max_workers):
                    await task_queue.put(None)

                # 워커 종료 대기
                await asyncio.gather(*workers)

            # 마지막 페이지 완료 처리
            if page_items > 0:
                self.crawl_logger.page_progress(
                    current_page,
                    self.state_manager.state.progress.total_pages,
                    page_items,
                )
                if self._on_page_completed:
                    self._on_page_completed(
                        current_page,
                        self.state_manager.state.progress.total_pages,
                    )

            # 완료 처리
            self.state_manager.mark_completed()

    def _log_statistics(self) -> None:
        """통계 로깅"""
        stats = self.state_manager.get_statistics()
        self.crawl_logger.end_crawl(
            total=stats.total_collected,
            success=stats.total_collected - stats.errors,
            errors=stats.errors,
            duplicates=stats.skipped_duplicates,
        )


# === Helper Function ===

async def run_crawler(
    config: Optional[CrawlerConfig] = None,
    resume: bool = True,
    repository: Optional[BidRepositoryProtocol] = None,
) -> CrawlState:
    """
    크롤러 실행 헬퍼 함수

    Args:
        config: 크롤러 설정
        resume: 이전 상태에서 재시작 여부
        repository: 저장소 인스턴스 (DI)

    Returns:
        최종 크롤링 상태
    """
    crawler = BidCrawler(config, repository=repository)
    return await crawler.run(resume=resume)
