import asyncio
from typing import (
    Any,
    AsyncGenerator,
)

from port_ocean.utils.async_iterators import stream_async_iterators_tasks


async def iterate_per_page(
    page_generator_callable: Any,
    page_dependent_callable: Any,
    sem: asyncio.Semaphore,
    *args: Any,
    **kwargs: Any,
) -> AsyncGenerator[Any, None]:
    async with sem:
        async for elements_page in page_generator_callable():
            tasks: Any = [
                page_dependent_callable(element, *args, **kwargs)
                for element in elements_page
            ]
            async for results in stream_async_iterators_tasks(*tasks):
                if results:
                    yield results
