import asyncio
from asyncio import Queue, Task
from typing import Any, TypeVar, Callable, Awaitable

T = TypeVar("T")
P = TypeVar("P")


async def _start_processor_worker(
    queue: Queue[Any | None],
    func: Callable[[P, ...], Awaitable[T]],
    results: list[T],
) -> None:
    while True:
        raw_params = await queue.get()
        try:
            if raw_params is None:
                return
            results.append(await func(*raw_params))
        finally:
            queue.task_done()


async def process_in_queue(
    objects_to_process: list[P],
    func: Callable[[P, ...], Awaitable[T]],
    *args,
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
        await queue.put((objects_to_process[i], *args))

    for i in range(concurrency):
        await queue.put(None)

    await queue.join()
    await asyncio.gather(*tasks)

    return processing_results
