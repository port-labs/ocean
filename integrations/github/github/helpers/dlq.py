import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import httpx
from loguru import logger

_RATE_LIMIT_STATUS_CODES = {403, 429}


@dataclass
class DLQEntry:
    description: str
    retry: Callable[[], Awaitable[Any]]


class RateLimitDLQ:
    """Dead letter queue for operations that failed due to rate limiting (403/429).

    Stores lightweight retry callables so it can be used across any resync kind
    without coupling to a specific exporter or data model.  Entries are retried
    once at the end of the resync when the rate-limit window has likely recovered.
    """

    def __init__(self) -> None:
        self._entries: list[DLQEntry] = []

    def add(
        self,
        description: str,
        retry: Callable[[], Awaitable[Any]],
    ) -> None:
        logger.warning(f"DLQ: deferring {description}")
        self._entries.append(DLQEntry(description=description, retry=retry))

    async def retry_all(self) -> list[Any]:
        """Retry every queued entry concurrently.

        Returns only the successful results; persistent failures are logged
        and discarded so the resync can still complete with partial data.
        """
        if not self._entries:
            return []

        logger.info(f"Retrying {len(self._entries)} rate-limited items from DLQ")

        results = await asyncio.gather(
            *[entry.retry() for entry in self._entries],
            return_exceptions=True,
        )

        successful = [r for r in results if not isinstance(r, BaseException)]
        failed = [r for r in results if isinstance(r, BaseException)]

        if failed:
            for err in failed:
                logger.warning(f"DLQ retry failed: {err}")
            logger.warning(
                f"DLQ retry: {len(failed)}/{len(self._entries)} items still failed"
            )

        self._entries.clear()
        return successful

    @property
    def is_empty(self) -> bool:
        return len(self._entries) == 0

    @property
    def size(self) -> int:
        return len(self._entries)


async def with_dlq_on_rate_limit(
    factory: Callable[[], AsyncIterator[list[Any]]],
    dlq: RateLimitDLQ,
    description: str,
) -> AsyncIterator[list[Any]]:
    """Iterate an async generator produced by *factory*, catching rate-limit
    errors (403/429) at the task level.

    On a rate-limit error the *entire* operation is deferred to the DLQ for
    retry at the end of the resync.  Non-rate-limit errors propagate normally.

    Items already yielded before the error are kept (the Ocean framework
    upserts, so duplicates during the retry are harmless).
    """
    try:
        async for batch in factory():
            yield batch
    except httpx.HTTPStatusError as e:
        if e.response.status_code in _RATE_LIMIT_STATUS_CODES:

            async def _retry() -> list[Any]:
                results: list[Any] = []
                async for batch in factory():
                    results.extend(batch)
                return results

            dlq.add(description=description, retry=_retry)
        else:
            raise
