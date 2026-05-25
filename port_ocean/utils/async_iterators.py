import asyncio
import typing
from dataclasses import dataclass

import aiostream
from loguru import logger

CANCELLED_TASK_CLEANUP_TIMEOUT = 10

T = typing.TypeVar("T")


@dataclass(slots=True)
class _IteratorItem(typing.Generic[T]):
    item: T


@dataclass(slots=True)
class _IteratorFinished:
    error: Exception | None = None


if typing.TYPE_CHECKING:
    from asyncio import Semaphore


async def stream_async_iterators_tasks(
    *tasks: typing.AsyncIterable[typing.Any],
) -> typing.AsyncIterable[typing.Any]:
    """
    This function takes a list of async iterators and streams the results of each iterator as they are available.
    By using this function you can combine multiple async iterators into a single stream of results, instead of waiting
    for each iterator to finish before starting the next one.

    Usage:
    ```python
    async def async_iterator1():
        for i in range(10):
            yield i
            await asyncio.sleep(1)

    async def async_iterator2():
        for i in range(10, 20):
            yield i
            await asyncio.sleep(1)

    async def main():
        async for result in stream_async_iterators_tasks([async_iterator1(), async_iterator2()]):
            print(result)
    ```

    Caution - Before using this function, make sure that the third-party API you are calling allows the number of
    concurrent requests you are making. If the API has a rate limit, you may need to adjust the number of concurrent
    requests to avoid hitting the rate limit.

    :param tasks: A list of async iterators
    :return: A stream of results
    """
    if not tasks:
        return

    if len(tasks) == 1:
        async for batch_items in tasks[0]:
            yield batch_items
        return

    combine = aiostream.stream.merge(tasks[0], *tasks[1:])
    async with combine.stream() as streamer:
        async for batch_items in streamer:
            yield batch_items


async def semaphore_async_iterator(
    semaphore: "Semaphore",
    function: typing.Callable[[], typing.AsyncIterator[typing.Any]],
) -> typing.AsyncIterator[typing.Any]:
    """
    Executes an asynchronous iterator function under a semaphore to limit concurrency.

    This function ensures that the provided asynchronous iterator function is executed
    while respecting the concurrency limit imposed by the semaphore. It acquires the
    semaphore before executing the function and releases it after the function completes,
    thus controlling the number of concurrent executions.

    Parameters:
        semaphore (asyncio.Semaphore | asyncio.BoundedSemaphore): The semaphore used to limit concurrency.
        function (Callable[[], AsyncIterator[Any]]): A nullary asynchronous function, - apply arguments with `functools.partial` or an anonymous function (lambda)
            that returns an asynchronous iterator. This function is executed under the semaphore.

    Yields:
        Any: The items yielded by the asynchronous iterator function.

    Usage:
        ```python
        import asyncio

        async def async_iterator_function(param1, param2):
            # Your async code here
            yield ...

        async def async_generator_function():
            # Your async code to retrieve items
            param1 = "your_param1"
            yield param1

        async def main():
            semaphore = asyncio.BoundedSemaphore(50)
            param2 = "your_param2"

            tasks = [
                semaphore_async_iterator(
                    semaphore,
                    lambda: async_iterator_function(param1, param2) # functools.partial(async_iterator_function, param1, param2)
                )
                async for param1 in async_generator_function()
            ]

            async for batch in stream_async_iterators_tasks(*tasks):
                # Process each batch
                pass

        asyncio.run(main())
        ```
    """
    async with semaphore:
        async for result in function():
            yield result


async def _consume_iterator(
    *,
    index: int,
    iterator: typing.AsyncIterable[T],
    queue: asyncio.Queue[_IteratorItem[T] | _IteratorFinished],
    is_closing: asyncio.Event,
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
        if is_closing.is_set():
            return

        await queue.put(_IteratorFinished(error=error))


async def stream_independent_async_iterators(
    *iterators: typing.AsyncIterable[T], context: str
) -> typing.AsyncGenerator[T, None]:
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

    queue: asyncio.Queue[_IteratorItem[T] | _IteratorFinished] = asyncio.Queue(
        maxsize=max(len(iterators) * 2, 32)
    )

    errors: list[Exception] = []
    is_closing = asyncio.Event()

    tasks = [
        asyncio.create_task(
            _consume_iterator(
                index=index,
                iterator=iterator,
                queue=queue,
                is_closing=is_closing,
                context=context,
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
        is_closing.set()
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
                f"{context} cleanup timed out after "
                f"{CANCELLED_TASK_CLEANUP_TIMEOUT} seconds while waiting "
                f"for {len(pending)} cancelled iterator task(s)"
            )

    if errors:
        raise ExceptionGroup(
            f"{context} failed with {len(errors)} error(s)",
            errors,
        )
