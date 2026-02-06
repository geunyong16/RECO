"""
retry.py 단위 테스트

재시도 로직을 테스트합니다.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bid_crawler.utils.retry import (
    RetryContext,
    RetryError,
    retry_async,
    with_retry,
)


class TestRetryAsync:
    """retry_async 함수 테스트"""

    @pytest.mark.asyncio
    async def test_success_on_first_try(self) -> None:
        """첫 번째 시도에서 성공"""
        mock_func = AsyncMock(return_value="success")

        result = await retry_async(mock_func)

        assert result == "success"
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_success_after_retries(self) -> None:
        """재시도 후 성공"""
        mock_func = AsyncMock(side_effect=[Exception("fail"), Exception("fail"), "success"])

        result = await retry_async(mock_func, max_retries=3, base_delay=0.01)

        assert result == "success"
        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self) -> None:
        """최대 재시도 횟수 초과"""
        mock_func = AsyncMock(side_effect=Exception("always fail"))

        with pytest.raises(RetryError) as exc_info:
            await retry_async(mock_func, max_retries=3, base_delay=0.01)

        assert exc_info.value.attempts == 3
        assert "always fail" in str(exc_info.value.last_exception)

    @pytest.mark.asyncio
    async def test_exponential_backoff(self) -> None:
        """지수 백오프 테스트"""
        mock_func = AsyncMock(side_effect=[Exception("fail"), "success"])
        delays: list[float] = []

        async def mock_sleep(delay: float) -> None:
            delays.append(delay)

        with patch("asyncio.sleep", mock_sleep):
            await retry_async(
                mock_func,
                max_retries=3,
                base_delay=1.0,
                exponential_backoff=True,
                jitter=False,
            )

        # 첫 번째 재시도 대기 시간: base_delay * 2^0 = 1.0
        assert len(delays) == 1
        assert delays[0] == 1.0

    @pytest.mark.asyncio
    async def test_no_exponential_backoff(self) -> None:
        """지수 백오프 비활성화 테스트"""
        mock_func = AsyncMock(side_effect=[Exception("fail"), Exception("fail"), "success"])
        delays: list[float] = []

        async def mock_sleep(delay: float) -> None:
            delays.append(delay)

        with patch("asyncio.sleep", mock_sleep):
            await retry_async(
                mock_func,
                max_retries=3,
                base_delay=1.0,
                exponential_backoff=False,
                jitter=False,
            )

        # 모든 대기 시간이 동일해야 함
        assert all(d == 1.0 for d in delays)

    @pytest.mark.asyncio
    async def test_jitter(self) -> None:
        """지터 테스트"""
        mock_func = AsyncMock(side_effect=[Exception("fail"), "success"])
        delays: list[float] = []

        async def mock_sleep(delay: float) -> None:
            delays.append(delay)

        with patch("asyncio.sleep", mock_sleep):
            await retry_async(
                mock_func,
                max_retries=3,
                base_delay=1.0,
                exponential_backoff=False,
                jitter=True,
            )

        # 지터로 인해 대기 시간이 0.5 ~ 1.5 사이여야 함
        assert len(delays) == 1
        assert 0.5 <= delays[0] <= 1.5

    @pytest.mark.asyncio
    async def test_max_delay(self) -> None:
        """최대 대기 시간 테스트"""
        mock_func = AsyncMock(
            side_effect=[Exception("fail")] * 10 + ["success"]
        )
        delays: list[float] = []

        async def mock_sleep(delay: float) -> None:
            delays.append(delay)

        with patch("asyncio.sleep", mock_sleep):
            await retry_async(
                mock_func,
                max_retries=11,
                base_delay=1.0,
                max_delay=5.0,
                exponential_backoff=True,
                jitter=False,
            )

        # 최대 대기 시간을 초과하지 않아야 함
        assert all(d <= 5.0 for d in delays)

    @pytest.mark.asyncio
    async def test_on_retry_callback(self) -> None:
        """재시도 콜백 테스트"""
        mock_func = AsyncMock(side_effect=[Exception("fail"), "success"])
        callback_calls: list[tuple[int, Exception]] = []

        def on_retry(attempt: int, exception: Exception) -> None:
            callback_calls.append((attempt, exception))

        await retry_async(
            mock_func,
            max_retries=3,
            base_delay=0.01,
            on_retry=on_retry,
        )

        assert len(callback_calls) == 1
        assert callback_calls[0][0] == 1
        assert "fail" in str(callback_calls[0][1])

    @pytest.mark.asyncio
    async def test_specific_exceptions(self) -> None:
        """특정 예외만 재시도"""

        class RetryableError(Exception):
            pass

        class NonRetryableError(Exception):
            pass

        # RetryableError는 재시도
        mock_func = AsyncMock(side_effect=[RetryableError("retry"), "success"])
        result = await retry_async(
            mock_func,
            max_retries=3,
            base_delay=0.01,
            retry_exceptions=(RetryableError,),
        )
        assert result == "success"

        # NonRetryableError는 재시도 안 함
        mock_func = AsyncMock(side_effect=NonRetryableError("no retry"))
        with pytest.raises(NonRetryableError):
            await retry_async(
                mock_func,
                max_retries=3,
                base_delay=0.01,
                retry_exceptions=(RetryableError,),
            )


class TestWithRetryDecorator:
    """with_retry 데코레이터 테스트"""

    @pytest.mark.asyncio
    async def test_decorator_success(self) -> None:
        """데코레이터 성공 케이스"""
        call_count = 0

        @with_retry(max_retries=3, base_delay=0.01)
        async def flaky_function() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("temporary failure")
            return "success"

        result = await flaky_function()
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_decorator_failure(self) -> None:
        """데코레이터 실패 케이스"""

        @with_retry(max_retries=2, base_delay=0.01)
        async def always_fail() -> str:
            raise Exception("always fail")

        with pytest.raises(RetryError):
            await always_fail()


class TestRetryContext:
    """RetryContext 컨텍스트 매니저 테스트"""

    @pytest.mark.asyncio
    async def test_context_success(self) -> None:
        """컨텍스트 매니저 성공 케이스"""
        async with RetryContext(max_retries=3, base_delay=0.01) as ctx:
            result = await ctx.execute(AsyncMock(return_value="success"))

        assert result == "success"
        assert ctx.attempts == 1

    @pytest.mark.asyncio
    async def test_context_with_retries(self) -> None:
        """컨텍스트 매니저 재시도 케이스"""
        mock_func = AsyncMock(side_effect=[Exception("fail"), "success"])

        async with RetryContext(max_retries=3, base_delay=0.01) as ctx:
            result = await ctx.execute(mock_func)

        assert result == "success"
        assert ctx.attempts == 2

    @pytest.mark.asyncio
    async def test_context_failure(self) -> None:
        """컨텍스트 매니저 실패 케이스"""
        mock_func = AsyncMock(side_effect=Exception("always fail"))

        with pytest.raises(RetryError):
            async with RetryContext(max_retries=2, base_delay=0.01) as ctx:
                await ctx.execute(mock_func)


class TestRetryError:
    """RetryError 예외 테스트"""

    def test_retry_error_attributes(self) -> None:
        """RetryError 속성 테스트"""
        original_error = ValueError("original")
        error = RetryError(
            message="Max retries exceeded",
            attempts=3,
            last_exception=original_error,
        )

        assert error.attempts == 3
        assert error.last_exception == original_error
        assert "Max retries exceeded" in str(error)
