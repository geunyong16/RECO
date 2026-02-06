"""
유틸리티 모듈 테스트

retry, logger 등 유틸리티의 동작을 검증합니다.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock

from bid_crawler.utils.retry import retry_async, RetryError, RetryContext


class TestRetryAsync:
    """retry_async 테스트"""

    @pytest.mark.asyncio
    async def test_success_first_try(self):
        """첫 시도 성공"""
        func = AsyncMock(return_value="success")
        result = await retry_async(func, max_retries=3)

        assert result == "success"
        assert func.call_count == 1

    @pytest.mark.asyncio
    async def test_success_after_retry(self):
        """재시도 후 성공"""
        func = AsyncMock(side_effect=[Exception("error"), Exception("error"), "success"])
        result = await retry_async(func, max_retries=3, base_delay=0.01)

        assert result == "success"
        assert func.call_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """최대 재시도 초과"""
        func = AsyncMock(side_effect=Exception("always fails"))

        with pytest.raises(RetryError) as exc_info:
            await retry_async(func, max_retries=2, base_delay=0.01)

        assert exc_info.value.attempts == 3
        assert func.call_count == 3

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """지수 백오프"""
        delays = []

        def record_retry(attempt, error):
            delays.append(attempt)

        func = AsyncMock(side_effect=[Exception("e1"), Exception("e2"), "success"])
        await retry_async(
            func,
            max_retries=3,
            base_delay=0.01,
            exponential_backoff=True,
            on_retry=record_retry,
        )

        assert delays == [1, 2]

    @pytest.mark.asyncio
    async def test_specific_exceptions(self):
        """특정 예외만 재시도"""
        func = AsyncMock(side_effect=ValueError("not retryable"))

        with pytest.raises(RetryError):
            await retry_async(
                func,
                max_retries=2,
                base_delay=0.01,
                retry_exceptions=(ValueError,),
            )


class TestRetryContext:
    """RetryContext 테스트"""

    @pytest.mark.asyncio
    async def test_success_loop(self):
        """성공 루프"""
        attempts = 0

        async with RetryContext(max_retries=3, base_delay=0.01) as ctx:
            while ctx.should_retry():
                attempts += 1
                if attempts == 2:
                    break
                await ctx.handle_error(Exception("retry"))

        assert attempts == 2

    @pytest.mark.asyncio
    async def test_max_retries(self):
        """최대 재시도"""
        async with RetryContext(max_retries=2, base_delay=0.01) as ctx:
            with pytest.raises(RetryError):
                while ctx.should_retry():
                    await ctx.handle_error(Exception("always fails"))
