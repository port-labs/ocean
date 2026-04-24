from asyncio import BoundedSemaphore
from functools import partial
from typing import Any

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_async_iterators_tasks,
)

from gcp_core.helpers.ratelimiter.base import MAXIMUM_CONCURRENT_REQUESTS
from gcp_core.search.resource_searches import search_all_projects


async def iterate_per_available_project(
    project_dependent_callable: Any,
    *args: Any,
    max_concurrent_projects: int = MAXIMUM_CONCURRENT_REQUESTS,
    **kwargs: Any,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    semaphore = BoundedSemaphore(max_concurrent_projects)
    try:
        async for projects in search_all_projects():

            tasks = [
                semaphore_async_iterator(
                    semaphore,
                    partial(project_dependent_callable, project, *args, **kwargs),
                )
                for project in projects
            ]
            if not tasks:
                logger.warning(
                    f"Searched {len(projects)} projects and found no accessible resources for {kwargs.get('asset_type')}. This may be due to unset permissions or no currently existing projects."
                )
                return

            async for batch in stream_async_iterators_tasks(*tasks):
                yield batch
    except Exception as e:
        logger.exception(f"Error iterating over projects: {e}")
