"""Retry classification and bounded exponential backoff for async adapters."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import inspect
import random
from typing import Awaitable, Callable, Iterable, TypeVar

from integrations.common import ProviderError, RunCancelled, RunTimeout


T = TypeVar("T")
Sleep = Callable[[float], Awaitable[None]]
RetryCallback = Callable[[int, Exception, float], Awaitable[None] | None]


@dataclass(frozen=True)
class RetryPolicy:
    """Configuration for bounded exponential retry delays."""

    max_attempts: int = 3
    base_delay: float = 0.5
    max_delay: float = 8.0
    jitter: float = 0.1
    retryable_status_codes: frozenset[int] = field(
        default_factory=lambda: frozenset({429, 500, 502, 503, 504})
    )

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts 必须大于 0")
        if self.base_delay < 0:
            raise ValueError("base_delay 不能小于 0")
        if self.max_delay < self.base_delay:
            raise ValueError("max_delay 不能小于 base_delay")
        if self.jitter < 0:
            raise ValueError("jitter 不能小于 0")

    def delay_for(self, attempt: int) -> float:
        """Return the delay before the next attempt, bounded by max_delay."""

        if attempt < 1:
            raise ValueError("attempt 必须从 1 开始")
        exponential = min(self.max_delay, self.base_delay * (2 ** (attempt - 1)))
        if self.jitter == 0:
            return exponential
        return min(self.max_delay, exponential + random.uniform(0, exponential * self.jitter))


def is_retryable_error(
    error: Exception,
    *,
    retryable_status_codes: Iterable[int] = (429, 500, 502, 503, 504),
) -> bool:
    """Return whether retrying the operation can reasonably succeed later."""

    if isinstance(error, RunCancelled):
        return False
    if isinstance(error, ProviderError):
        return error.status_code in set(retryable_status_codes)
    return isinstance(error, (RunTimeout, TimeoutError, ConnectionError))


async def retry_async(
    operation: Callable[[int], Awaitable[T]],
    *,
    policy: RetryPolicy,
    on_retry: RetryCallback | None = None,
    sleep: Sleep = asyncio.sleep,
) -> T:
    """Run an async operation, retrying only classified transient failures."""

    for attempt in range(1, policy.max_attempts + 1):
        try:
            return await operation(attempt)
        except RunCancelled:
            raise
        except Exception as error:
            if attempt >= policy.max_attempts or not is_retryable_error(
                error,
                retryable_status_codes=policy.retryable_status_codes,
            ):
                raise

            delay = policy.delay_for(attempt)
            if on_retry is not None:
                callback_result = on_retry(attempt, error, delay)
                if inspect.isawaitable(callback_result):
                    await callback_result
            await sleep(delay)

    raise RuntimeError("retry_async 意外退出")
