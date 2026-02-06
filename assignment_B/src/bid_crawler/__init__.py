"""
누리장터 입찰공고 크롤러 패키지

동적으로 렌더링되는 입찰공고 페이지에서 목록 및 상세 정보를 수집하여
표준 스키마로 저장하는 크롤러입니다.

주요 기능:
- 동적 웹페이지 크롤링 (Playwright 기반)
- 목록 → 상세 페이지 자동 탐색
- 중단점 저장 및 재시작 지원
- 중복 방지 및 재시도 로직
- interval/cron 스케줄링 지원
"""

__version__ = "1.0.0"
__author__ = "Your Name"

from bid_crawler.crawler import BidCrawler
from bid_crawler.models.bid_notice import BidNotice, BidNoticeDetail
from bid_crawler.config import CrawlerConfig

__all__ = [
    "BidCrawler",
    "BidNotice",
    "BidNoticeDetail",
    "CrawlerConfig",
]
