from typing import Any

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import stream_async_iterators_tasks


async def iterate_per_page(
    page_generator_callable: Any,
    page_dependent_callable: Any,
    *args: Any,
    **kwargs: Any,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for elements_page in page_generator_callable():
        tasks = [
            page_dependent_callable(element, *args, **kwargs)
            for element in elements_page
        ]
        async for batch in stream_async_iterators_tasks(*tasks):
            yield batch
