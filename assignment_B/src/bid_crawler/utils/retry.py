"""
재시도 로직 모듈

네트워크 오류, 타임아웃 등의 일시적 장애에 대한 재시도 로직을 제공합니다.
지수 백오프(exponential backoff)를 지원합니다.
"""

import asyncio
import functools
import random
from typing import Callable, TypeVar, Any, Optional, Tuple, Type
from datetime import datetime

from bid_crawler.utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class RetryError(Exception):
    """재시도 실패 예외"""

    def __init__(
        self,
        message: str,
        attempts: int,
        last_exception: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.attempts = attempts
        self.last_exception = last_exception


async def retry_async(
    func: Callable[..., T],
    *args: Any,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_backoff: bool = True,
    jitter: bool = True,
    retry_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[int, Exception], None]] = None,
    **kwargs: Any,
) -> T:
    """
    비동기 함수 재시도 실행

    Args:
        func: 실행할 비동기 함수
        *args: 함수 인자
        max_retries: 최대 재시도 횟수
        base_delay: 기본 대기 시간 (초)
        max_delay: 최대 대기 시간 (초)
        exponential_backoff: 지수 백오프 적용 여부
        jitter: 랜덤 지터 적용 여부 (thundering herd 방지)
        retry_exceptions: 재시도할 예외 타입들
        on_retry: 재시도 시 콜백 함수 (attempt, exception)
        **kwargs: 함수 키워드 인자

    Returns:
        함수 실행 결과

    Raises:
        RetryError: 모든 재시도 실패 시
    """
    last_exception: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)

        except retry_exceptions as e:
            last_exception = e

            if attempt == max_retries:
                logger.error(
                    f"모든 재시도 실패 ({max_retries + 1}회 시도): {e}"
                )
                raise RetryError(
                    f"최대 재시도 횟수({max_retries})를 초과했습니다",
                    attempts=attempt + 1,
                    last_exception=e,
                )

            # 대기 시간 계산
            if exponential_backoff:
                delay = min(base_delay * (2 ** attempt), max_delay)
            else:
                delay = base_delay

            # 지터 추가 (0.5 ~ 1.5 배)
            if jitter:
                delay = delay * (0.5 + random.random())

            logger.warning(
                f"재시도 {attempt + 1}/{max_retries}: {e.__class__.__name__}: {e} "
                f"({delay:.1f}초 후 재시도)"
            )

            if on_retry:
                on_retry(attempt + 1, e)

            await asyncio.sleep(delay)

    # 이 코드는 실행되지 않아야 함 (위에서 raise)
    raise RetryError(
        "예상치 못한 재시도 루프 종료",
        attempts=max_retries + 1,
        last_exception=last_exception,
    )


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_backoff: bool = True,
    retry_exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    재시도 데코레이터

    Usage:
        @with_retry(max_retries=3)
        async def fetch_data():
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await retry_async(
                func,
                *args,
                max_retries=max_retries,
                base_delay=base_delay,
                max_delay=max_delay,
                exponential_backoff=exponential_backoff,
                retry_exceptions=retry_exceptions,
                **kwargs,
            )
        return wrapper
    return decorator


class RetryContext:
    """
    재시도 컨텍스트 매니저

    Usage:
        async with RetryContext(max_retries=3) as ctx:
            while ctx.should_retry():
                try:
                    result = await some_operation()
                    break
                except Exception as e:
                    await ctx.handle_error(e)
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_backoff: bool = True,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_backoff = exponential_backoff
        self.attempt = 0
        self.last_exception: Optional[Exception] = None

    async def __aenter__(self) -> "RetryContext":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        return False

    def should_retry(self) -> bool:
        """재시도 가능 여부"""
        return self.attempt <= self.max_retries

    @property
    def attempts(self) -> int:
        """현재까지 시도 횟수"""
        return self.attempt

    async def execute(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """
        함수 실행 및 재시도

        Args:
            func: 실행할 함수
            *args: 함수 인자
            **kwargs: 함수 키워드 인자

        Returns:
            함수 실행 결과
        """
        return await retry_async(
            func,
            *args,
            max_retries=self.max_retries,
            base_delay=self.base_delay,
            max_delay=self.max_delay,
            exponential_backoff=self.exponential_backoff,
            **kwargs,
        )

    async def handle_error(self, error: Exception) -> None:
        """오류 처리 및 대기"""
        self.last_exception = error
        self.attempt += 1

        if self.attempt > self.max_retries:
            raise RetryError(
                f"최대 재시도 횟수({self.max_retries})를 초과했습니다",
                attempts=self.attempt,
                last_exception=error,
            )

        # 대기 시간 계산
        if self.exponential_backoff:
            delay = min(self.base_delay * (2 ** (self.attempt - 1)), self.max_delay)
        else:
            delay = self.base_delay

        # 지터 추가
        delay = delay * (0.5 + random.random())

        logger.warning(
            f"재시도 {self.attempt}/{self.max_retries}: {error} "
            f"({delay:.1f}초 후 재시도)"
        )

        await asyncio.sleep(delay)
