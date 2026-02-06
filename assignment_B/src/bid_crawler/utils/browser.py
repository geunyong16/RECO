"""
브라우저 관리 모듈

Playwright를 사용한 브라우저 인스턴스 관리를 담당합니다.
"""

import asyncio
from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeout,
)

from bid_crawler.config import BrowserConfig
from bid_crawler.utils.logger import get_logger

logger = get_logger(__name__)


class BrowserManager:
    """
    브라우저 생명주기 관리자

    Playwright 브라우저의 시작, 종료, 페이지 관리를 담당합니다.
    """

    def __init__(self, config: Optional[BrowserConfig] = None):
        self.config = config or BrowserConfig()
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    async def start(self) -> None:
        """브라우저 시작"""
        if self._browser is not None:
            logger.warning("브라우저가 이미 실행 중입니다")
            return

        logger.info("브라우저 시작 중...")

        self._playwright = await async_playwright().start()

        # Chromium 브라우저 실행
        self._browser = await self._playwright.chromium.launch(
            headless=self.config.headless,
            slow_mo=self.config.slow_mo,
        )

        # 브라우저 컨텍스트 생성 (세션 격리)
        self._context = await self._browser.new_context(
            viewport={
                "width": self.config.viewport_width,
                "height": self.config.viewport_height,
            },
            locale="ko-KR",
            timezone_id="Asia/Seoul",
        )

        # 기본 타임아웃 설정
        self._context.set_default_timeout(self.config.timeout)

        logger.info(
            f"브라우저 시작 완료 (headless={self.config.headless}, "
            f"timeout={self.config.timeout}ms)"
        )

    async def stop(self) -> None:
        """브라우저 종료"""
        if self._context:
            await self._context.close()
            self._context = None

        if self._browser:
            await self._browser.close()
            self._browser = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

        logger.info("브라우저 종료 완료")

    async def new_page(self) -> Page:
        """새 페이지 생성"""
        if self._context is None:
            raise RuntimeError("브라우저가 시작되지 않았습니다. start()를 먼저 호출하세요.")

        page = await self._context.new_page()

        # 불필요한 리소스 차단 (선택적 최적화)
        # await page.route("**/*.{png,jpg,jpeg,gif,svg,ico}", lambda route: route.abort())

        return page

    @asynccontextmanager
    async def get_page(self) -> AsyncGenerator[Page, None]:
        """
        페이지 컨텍스트 매니저

        Usage:
            async with browser_manager.get_page() as page:
                await page.goto(url)
        """
        page = await self.new_page()
        try:
            yield page
        finally:
            await page.close()

    async def __aenter__(self) -> "BrowserManager":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()


async def wait_for_navigation_complete(
    page: Page,
    timeout: int = 30000,
) -> None:
    """
    페이지 로드 완료 대기

    네트워크 요청이 멈출 때까지 대기합니다.
    """
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout)
    except PlaywrightTimeout:
        logger.warning("페이지 로드 타임아웃 - 계속 진행")


async def safe_click(
    page: Page,
    selector: str,
    wait_after: int = 1000,
    timeout: int = 10000,
) -> bool:
    """
    안전한 클릭

    요소가 존재하고 클릭 가능할 때만 클릭합니다.

    Returns:
        클릭 성공 여부
    """
    try:
        element = await page.wait_for_selector(selector, timeout=timeout)
        if element:
            await element.click()
            await asyncio.sleep(wait_after / 1000)
            return True
    except PlaywrightTimeout:
        logger.warning(f"요소를 찾을 수 없음: {selector}")
    except Exception as e:
        logger.warning(f"클릭 실패 ({selector}): {e}")

    return False


async def safe_fill(
    page: Page,
    selector: str,
    value: str,
    timeout: int = 10000,
) -> bool:
    """
    안전한 입력

    Returns:
        입력 성공 여부
    """
    try:
        element = await page.wait_for_selector(selector, timeout=timeout)
        if element:
            await element.fill(value)
            return True
    except PlaywrightTimeout:
        logger.warning(f"입력 요소를 찾을 수 없음: {selector}")
    except Exception as e:
        logger.warning(f"입력 실패 ({selector}): {e}")

    return False


async def get_text_content(
    page: Page,
    selector: str,
    default: str = "",
    timeout: int = 5000,
) -> str:
    """
    텍스트 추출

    Returns:
        추출된 텍스트 또는 기본값
    """
    try:
        element = await page.wait_for_selector(selector, timeout=timeout)
        if element:
            text = await element.text_content()
            return text.strip() if text else default
    except PlaywrightTimeout:
        pass
    except Exception as e:
        logger.debug(f"텍스트 추출 실패 ({selector}): {e}")

    return default


async def get_attribute(
    page: Page,
    selector: str,
    attribute: str,
    default: str = "",
    timeout: int = 5000,
) -> str:
    """
    속성 값 추출

    Returns:
        추출된 속성 값 또는 기본값
    """
    try:
        element = await page.wait_for_selector(selector, timeout=timeout)
        if element:
            value = await element.get_attribute(attribute)
            return value if value else default
    except PlaywrightTimeout:
        pass
    except Exception as e:
        logger.debug(f"속성 추출 실패 ({selector}@{attribute}): {e}")

    return default
