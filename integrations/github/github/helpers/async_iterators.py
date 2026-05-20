import asyncio
from collections.abc import AsyncIterable, AsyncIterator
from dataclasses import dataclass
from typing import Generic, TypeVar

from loguru import logger

T = TypeVar("T")


@dataclass(slots=True)
class _IteratorDone:
    pass


@dataclass(slots=True)
class _IteratorError:
    index: int
    error: Exception


@dataclass(slots=True)
class _IteratorItem(Generic[T]):
    item: T


async def stream_independent_async_iterators(
    *iterators: AsyncIterable[T], context: str = "GitHub independent iterator"
) -> AsyncIterator[T]:
    """Stream independent iterators while deferring their failures.

    A failed iterator should not stop other independent iterators from finishing. Any
    collected failures are raised after all surviving iterators are exhausted, allowing
    Ocean to mark the kind as incomplete and skip reconciliation deletes.
    """
    if not iterators:
        return

    queue: asyncio.Queue[_IteratorDone | _IteratorError | _IteratorItem[T]] = (
        asyncio.Queue(maxsize=len(iterators))
    )
    errors: list[Exception] = []

    async def consume(index: int, iterator: AsyncIterable[T]) -> None:
        try:
            async for item in iterator:
                await queue.put(_IteratorItem(item))
        except Exception as exc:
            logger.exception(
                f"{context} {index + 1} failed; continuing remaining siblings",
                exc_info=exc,
            )
            await queue.put(_IteratorError(index=index, error=exc))
        finally:
            await queue.put(_IteratorDone())

    tasks = [
        asyncio.create_task(consume(index, iterator))
        for index, iterator in enumerate(iterators)
    ]

    try:
        remaining = len(tasks)
        while remaining:
            message = await queue.get()
            if isinstance(message, _IteratorDone):
                remaining -= 1
            elif isinstance(message, _IteratorError):
                errors.append(message.error)
            else:
                yield message.item
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    if errors:
        raise ExceptionGroup(f"{context} failed with {len(errors)} error(s)", errors)
