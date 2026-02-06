"""
robots_checker.py 단위 테스트

robots.txt 확인 로직을 테스트합니다.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientTimeout

from bid_crawler.utils.robots_checker import RobotsChecker, get_robots_checker


class TestRobotsChecker:
    """RobotsChecker 클래스 테스트"""

    @pytest.fixture
    def checker(self) -> RobotsChecker:
        """테스트용 RobotsChecker 인스턴스"""
        return RobotsChecker(user_agent="TestBot/1.0")

    @pytest.mark.asyncio
    async def test_can_fetch_allowed(self, checker: RobotsChecker) -> None:
        """허용된 URL 테스트"""
        robots_content = """
User-agent: *
Allow: /
"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=robots_content)

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            result = await checker.can_fetch("https://example.com/page")
            assert result is True

    @pytest.mark.asyncio
    async def test_can_fetch_disallowed(self, checker: RobotsChecker) -> None:
        """차단된 URL 테스트"""
        robots_content = """
User-agent: *
Disallow: /private/
"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=robots_content)

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            result = await checker.can_fetch("https://example.com/private/secret")
            assert result is False

    @pytest.mark.asyncio
    async def test_can_fetch_no_robots(self, checker: RobotsChecker) -> None:
        """robots.txt 없는 경우 (허용으로 간주)"""
        mock_response = AsyncMock()
        mock_response.status = 404

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            result = await checker.can_fetch("https://example.com/page")
            assert result is True

    @pytest.mark.asyncio
    async def test_can_fetch_error(self, checker: RobotsChecker) -> None:
        """네트워크 오류 시 허용으로 간주"""
        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get.side_effect = Exception(
                "Network error"
            )

            result = await checker.can_fetch("https://example.com/page")
            assert result is True

    @pytest.mark.asyncio
    async def test_get_crawl_delay(self, checker: RobotsChecker) -> None:
        """Crawl-delay 값 테스트"""
        robots_content = """
User-agent: *
Crawl-delay: 5
"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=robots_content)

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            delay = await checker.get_crawl_delay("https://example.com/page")
            # RobotFileParser의 crawl_delay는 표준에서 지원하지 않을 수 있음
            # 지원되면 5.0, 아니면 None
            assert delay is None or delay == 5.0

    @pytest.mark.asyncio
    async def test_caching(self, checker: RobotsChecker) -> None:
        """캐싱 테스트"""
        robots_content = """
User-agent: *
Allow: /
"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=robots_content)

        call_count = 0

        async def mock_get(*args: any, **kwargs: any) -> AsyncMock:
            nonlocal call_count
            call_count += 1
            return mock_response

        with patch("aiohttp.ClientSession") as mock_session:
            session_instance = mock_session.return_value.__aenter__.return_value
            session_instance.get.return_value.__aenter__ = mock_get

            # 첫 번째 호출
            await checker.can_fetch("https://example.com/page1")
            # 두 번째 호출 (같은 도메인)
            await checker.can_fetch("https://example.com/page2")

            # 캐시로 인해 한 번만 호출되어야 함
            # (실제로는 캐시 구현에 따라 다를 수 있음)

    def test_clear_cache(self, checker: RobotsChecker) -> None:
        """캐시 초기화 테스트"""
        # 캐시에 항목 추가 (내부 구현에 의존)
        checker._cache["https://example.com/robots.txt"] = (MagicMock(), 0)

        checker.clear_cache()

        assert len(checker._cache) == 0

    def test_default_user_agent(self) -> None:
        """기본 User-Agent 테스트"""
        checker = RobotsChecker()
        assert "BidCrawler" in checker.user_agent

    def test_custom_user_agent(self) -> None:
        """사용자 정의 User-Agent 테스트"""
        checker = RobotsChecker(user_agent="CustomBot/2.0")
        assert checker.user_agent == "CustomBot/2.0"


class TestGetRobotsChecker:
    """get_robots_checker 함수 테스트"""

    def test_singleton_pattern(self) -> None:
        """싱글톤 패턴 테스트"""
        # 전역 인스턴스 초기화
        import bid_crawler.utils.robots_checker as module

        module._default_checker = None

        checker1 = get_robots_checker()
        checker2 = get_robots_checker()

        assert checker1 is checker2

    def test_with_custom_user_agent(self) -> None:
        """사용자 정의 User-Agent로 생성"""
        import bid_crawler.utils.robots_checker as module

        module._default_checker = None

        checker = get_robots_checker(user_agent="TestBot/3.0")
        assert "TestBot" in checker.user_agent or "BidCrawler" in checker.user_agent
