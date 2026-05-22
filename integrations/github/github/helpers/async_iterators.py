import asyncio
from collections.abc import AsyncGenerator, AsyncIterable
from dataclasses import dataclass
from typing import Generic, TypeVar

from loguru import logger
from github.helpers.utils import ObjectKind

T = TypeVar("T")

CANCELLED_TASK_CLEANUP_TIMEOUT = 10


@dataclass(slots=True)
class _IteratorItem(Generic[T]):
    item: T


@dataclass(slots=True)
class _IteratorFinished:
    error: Exception | None = None


async def _consume_iterator(
    *,
    index: int,
    iterator: AsyncIterable[T],
    queue: asyncio.Queue[_IteratorItem[T] | _IteratorFinished],
    context: str,
) -> None:
    error: Exception | None = None

    try:
        async for item in iterator:
            await queue.put(_IteratorItem(item))

    except asyncio.CancelledError:
        raise

    except Exception as exc:
        error = exc

        logger.exception(
            f"{context} iterator {index} failed; continuing remaining siblings"
        )

    finally:
        current_task = asyncio.current_task()

        if current_task and current_task.cancelling():
            return

        await queue.put(_IteratorFinished(error=error))


async def stream_independent_async_iterators(
    *iterators: AsyncIterable[T],
    context: ObjectKind | str = "GitHub Independent",
) -> AsyncGenerator[T, None]:
    """
    Stream multiple async iterators concurrently while deferring failures.

    Characteristics:
    - Items are yielded as they arrive.
    - Ordering is nondeterministic.
    - One iterator failing does not stop others.
    - Errors are raised as an ExceptionGroup after surviving iterators finish.
    - Errors are only surfaced if the stream is fully consumed.
    """
    if not iterators:
        return

    context_str = str(context)

    queue: asyncio.Queue[_IteratorItem[T] | _IteratorFinished] = asyncio.Queue(
        maxsize=max(len(iterators) * 2, 32)
    )

    errors: list[Exception] = []

    tasks = [
        asyncio.create_task(
            _consume_iterator(
                index=index,
                iterator=iterator,
                queue=queue,
                context=context_str,
            )
        )
        for index, iterator in enumerate(iterators)
    ]

    try:
        remaining = len(tasks)
        while remaining:
            message = await queue.get()

            if isinstance(message, _IteratorFinished):
                remaining -= 1

                if message.error is not None:
                    errors.append(message.error)
            else:
                yield message.item

    finally:
        for task in tasks:
            if not task.done():
                task.cancel()

        done, pending = await asyncio.wait(
            tasks,
            timeout=CANCELLED_TASK_CLEANUP_TIMEOUT,
        )

        await asyncio.gather(*done, return_exceptions=True)

        if pending:
            logger.warning(
                f"{context_str} cleanup timed out after "
                f"{CANCELLED_TASK_CLEANUP_TIMEOUT} seconds while waiting "
                f"for {len(pending)} cancelled iterator task(s)"
            )

    if errors:
        raise ExceptionGroup(
            f"{context_str} failed with {len(errors)} error(s)",
            errors,
        )
