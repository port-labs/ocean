import asyncio
from collections.abc import Awaitable, Callable, Iterable
from typing import TypeVar

T = TypeVar("T")

WEBHOOK_API_CONCURRENCY_LIMIT = 5


async def gather_with_concurrency_limit(
    fetch_functions: Iterable[Callable[[], Awaitable[T]]],
    concurrency_limit: int = WEBHOOK_API_CONCURRENCY_LIMIT,
) -> list[T]:
    semaphore = asyncio.Semaphore(concurrency_limit)

    async def run(fetch: Callable[[], Awaitable[T]]) -> T:
        async with semaphore:
            return await fetch()

    return list(await asyncio.gather(*(run(fetch) for fetch in fetch_functions)))
