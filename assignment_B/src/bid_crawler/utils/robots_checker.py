"""
robots.txt 확인 모듈

크롤링 윤리를 준수하기 위해 robots.txt를 확인합니다.
"""

import asyncio
from typing import Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import aiohttp

from bid_crawler.utils.logger import get_logger

logger = get_logger(__name__)


class RobotsChecker:
    """
    robots.txt 확인 클래스

    웹사이트의 robots.txt를 파싱하여 크롤링 허용 여부를 확인합니다.
    """

    DEFAULT_USER_AGENT = "BidCrawler/1.0 (+https://github.com/yourusername/bid-crawler)"
    CACHE_TTL = 3600  # 1시간

    def __init__(self, user_agent: Optional[str] = None) -> None:
        """
        Args:
            user_agent: 크롤러 User-Agent 문자열
        """
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT
        self._cache: dict[str, tuple[RobotFileParser, float]] = {}
        self._lock = asyncio.Lock()

    async def can_fetch(self, url: str) -> bool:
        """
        URL 크롤링 허용 여부 확인

        Args:
            url: 확인할 URL

        Returns:
            크롤링 허용 여부
        """
        try:
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            robots_url = urljoin(base_url, "/robots.txt")

            parser = await self._get_parser(robots_url)
            if parser is None:
                # robots.txt 없으면 허용으로 간주
                return True

            return parser.can_fetch(self.user_agent, url)

        except Exception as e:
            logger.warning(f"robots.txt 확인 실패 ({url}): {e}")
            # 실패 시 허용으로 간주 (보수적 접근 원하면 False 반환)
            return True

    async def get_crawl_delay(self, url: str) -> Optional[float]:
        """
        Crawl-delay 값 조회

        Args:
            url: 확인할 URL

        Returns:
            Crawl-delay 값 (초) 또는 None
        """
        try:
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            robots_url = urljoin(base_url, "/robots.txt")

            parser = await self._get_parser(robots_url)
            if parser is None:
                return None

            delay = parser.crawl_delay(self.user_agent)
            return float(delay) if delay else None

        except Exception as e:
            logger.warning(f"Crawl-delay 확인 실패 ({url}): {e}")
            return None

    async def _get_parser(self, robots_url: str) -> Optional[RobotFileParser]:
        """
        robots.txt 파서 가져오기 (캐싱 적용)

        Args:
            robots_url: robots.txt URL

        Returns:
            RobotFileParser 또는 None
        """
        import time

        async with self._lock:
            # 캐시 확인
            if robots_url in self._cache:
                parser, cached_at = self._cache[robots_url]
                if time.time() - cached_at < self.CACHE_TTL:
                    return parser

            # robots.txt 가져오기
            parser = await self._fetch_robots(robots_url)
            if parser:
                self._cache[robots_url] = (parser, time.time())

            return parser

    async def _fetch_robots(self, robots_url: str) -> Optional[RobotFileParser]:
        """
        robots.txt 내용 가져오기

        Args:
            robots_url: robots.txt URL

        Returns:
            RobotFileParser 또는 None
        """
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                headers = {"User-Agent": self.user_agent}
                async with session.get(robots_url, headers=headers) as response:
                    if response.status == 200:
                        content = await response.text()
                        parser = RobotFileParser()
                        parser.parse(content.splitlines())
                        logger.debug(f"robots.txt 로드 완료: {robots_url}")
                        return parser
                    elif response.status == 404:
                        logger.debug(f"robots.txt 없음: {robots_url}")
                        return None
                    else:
                        logger.warning(
                            f"robots.txt 가져오기 실패 ({response.status}): {robots_url}"
                        )
                        return None

        except asyncio.TimeoutError:
            logger.warning(f"robots.txt 타임아웃: {robots_url}")
            return None
        except Exception as e:
            logger.warning(f"robots.txt 가져오기 오류: {e}")
            return None

    def clear_cache(self) -> None:
        """캐시 초기화"""
        self._cache.clear()
        logger.debug("robots.txt 캐시 초기화됨")


# 전역 인스턴스
_default_checker: Optional[RobotsChecker] = None


def get_robots_checker(user_agent: Optional[str] = None) -> RobotsChecker:
    """
    기본 RobotsChecker 인스턴스 가져오기

    Args:
        user_agent: User-Agent (첫 호출 시에만 적용)

    Returns:
        RobotsChecker 인스턴스
    """
    global _default_checker
    if _default_checker is None:
        _default_checker = RobotsChecker(user_agent)
    return _default_checker
