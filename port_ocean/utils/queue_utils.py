import asyncio
from asyncio import Queue, Task
from typing import Any, TypeVar, Callable, Awaitable

from loguru import logger

T = TypeVar("T")


async def _start_processor_worker(
    queue: Queue[Any | None],
    func: Callable[[Any], Awaitable[T]],
    results: list[T],
) -> None:
    while True:
        raw_params = await queue.get()
        try:
            if raw_params is None:
                return
            logger.debug(f"Processing {raw_params[0]}")
            results.append(await func(*raw_params))
        finally:
            queue.task_done()


async def process_in_queue(
    objects_to_process: list[Any],
    func: Callable[[Any], Awaitable[T]],
    *args,
    item_override: Callable[[Any], Any] = lambda item: item,
    concurrency: int = 50,
) -> list[T]:
    queue: Queue[Any | None] = Queue(maxsize=concurrency * 2)
    tasks: list[Task[Any]] = []
    processing_results: list[T] = []

    for i in range(concurrency):
        tasks.append(
            asyncio.create_task(
                _start_processor_worker(queue, func, processing_results)
            )
        )

    for i in range(len(objects_to_process)):
        await queue.put((item_override(objects_to_process[i]), *args))

    for i in range(concurrency):
        await queue.put(None)

    await queue.join()
    await asyncio.gather(*tasks)

    return processing_results
