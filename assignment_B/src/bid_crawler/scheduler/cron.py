"""
스케줄러 모듈

정기적인 크롤링 실행을 위한 스케줄러를 제공합니다.
interval 모드와 cron 모드를 지원합니다.
"""

import asyncio
import signal
import sys
from typing import Optional, Callable
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from bid_crawler.config import CrawlerConfig, SchedulerConfig
from bid_crawler.crawler import BidCrawler
from bid_crawler.utils.logger import get_logger

logger = get_logger(__name__)


class CrawlScheduler:
    """
    크롤링 스케줄러

    주기적으로 크롤링을 실행합니다.
    - interval 모드: 일정 간격으로 실행
    - cron 모드: cron 표현식에 따라 실행
    """

    def __init__(
        self,
        crawler_config: Optional[CrawlerConfig] = None,
        scheduler_config: Optional[SchedulerConfig] = None,
    ):
        """
        Args:
            crawler_config: 크롤러 설정
            scheduler_config: 스케줄러 설정
        """
        self.crawler_config = crawler_config or CrawlerConfig()
        self.scheduler_config = scheduler_config or self.crawler_config.scheduler

        self._scheduler: Optional[AsyncIOScheduler] = None
        self._running = False
        self._on_crawl_complete: Optional[Callable] = None

    def on_crawl_complete(self, callback: Callable) -> None:
        """크롤링 완료 콜백 등록"""
        self._on_crawl_complete = callback

    async def _crawl_job(self) -> None:
        """스케줄러에서 실행되는 크롤링 작업"""
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        logger.info(f"=== 스케줄된 크롤링 시작: {run_id} ===")

        try:
            # 새 설정으로 크롤러 생성 (run_id 업데이트)
            config = self.crawler_config.model_copy()
            config.run_id = run_id

            crawler = BidCrawler(config)
            state = await crawler.run(resume=True)

            logger.info(
                f"=== 스케줄된 크롤링 완료: "
                f"{state.statistics.total_collected}건 수집 ==="
            )

            if self._on_crawl_complete:
                self._on_crawl_complete(state)

        except Exception as e:
            logger.error(f"스케줄된 크롤링 실패: {e}")

    def _create_trigger(self):
        """스케줄 트리거 생성"""
        if self.scheduler_config.mode == "interval":
            return IntervalTrigger(
                minutes=self.scheduler_config.interval_minutes
            )
        else:  # cron
            # cron 표현식 파싱: "분 시 일 월 요일"
            parts = self.scheduler_config.cron_expression.split()
            if len(parts) >= 5:
                return CronTrigger(
                    minute=parts[0],
                    hour=parts[1],
                    day=parts[2],
                    month=parts[3],
                    day_of_week=parts[4],
                )
            else:
                logger.warning(f"잘못된 cron 표현식: {self.scheduler_config.cron_expression}")
                # 기본값: 6시간마다
                return IntervalTrigger(hours=6)

    async def start(self, run_immediately: bool = True) -> None:
        """
        스케줄러 시작

        Args:
            run_immediately: True면 시작 시 즉시 한 번 실행
        """
        if self._running:
            logger.warning("스케줄러가 이미 실행 중입니다")
            return

        self._scheduler = AsyncIOScheduler()

        # 트리거 생성
        trigger = self._create_trigger()

        # 작업 등록
        self._scheduler.add_job(
            self._crawl_job,
            trigger=trigger,
            id="crawl_job",
            name="입찰공고 크롤링",
            replace_existing=True,
        )

        # 스케줄러 시작
        self._scheduler.start()
        self._running = True

        logger.info(
            f"스케줄러 시작됨 "
            f"(모드: {self.scheduler_config.mode}, "
            f"{'간격: ' + str(self.scheduler_config.interval_minutes) + '분' if self.scheduler_config.mode == 'interval' else 'cron: ' + self.scheduler_config.cron_expression})"
        )

        # 즉시 실행
        if run_immediately:
            logger.info("초기 크롤링 실행...")
            await self._crawl_job()

    def stop(self) -> None:
        """스케줄러 중지"""
        if self._scheduler and self._running:
            self._scheduler.shutdown(wait=False)
            self._running = False
            logger.info("스케줄러 중지됨")

    async def run_forever(self, run_immediately: bool = True) -> None:
        """
        스케줄러를 무한 실행

        Ctrl+C로 중지할 수 있습니다.
        """
        # 시그널 핸들러 등록
        def signal_handler(signum, frame):
            logger.info("중지 신호 수신...")
            self.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        await self.start(run_immediately=run_immediately)

        logger.info("스케줄러 실행 중... (Ctrl+C로 중지)")

        try:
            # 무한 대기
            while self._running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            self.stop()


async def run_scheduled(
    crawler_config: Optional[CrawlerConfig] = None,
    mode: str = "interval",
    interval_minutes: int = 60,
    cron_expression: str = "0 */6 * * *",
    run_immediately: bool = True,
) -> None:
    """
    스케줄된 크롤링 실행 헬퍼 함수

    Args:
        crawler_config: 크롤러 설정
        mode: 실행 모드 ("interval" 또는 "cron")
        interval_minutes: interval 모드 간격 (분)
        cron_expression: cron 표현식
        run_immediately: 시작 시 즉시 실행 여부
    """
    scheduler_config = SchedulerConfig(
        enabled=True,
        mode=mode,
        interval_minutes=interval_minutes,
        cron_expression=cron_expression,
    )

    scheduler = CrawlScheduler(
        crawler_config=crawler_config,
        scheduler_config=scheduler_config,
    )

    await scheduler.run_forever(run_immediately=run_immediately)
