"""스크래퍼 패키지"""

from bid_crawler.scrapers.base import BaseScraper, ScraperError
from bid_crawler.scrapers.list_scraper import ListScraper
from bid_crawler.scrapers.detail_scraper import DetailScraper

__all__ = [
    "BaseScraper",
    "ScraperError",
    "ListScraper",
    "DetailScraper",
]
