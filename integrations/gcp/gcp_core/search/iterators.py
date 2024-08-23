from typing import Any

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import stream_async_iterators_tasks

from gcp_core.errors import NoProjectsFoundError
from gcp_core.search.resource_searches import search_all_projects
from gcp_core.search.utils import rate_limiter
from loguru import logger


async def iterate_per_available_project(
    project_dependent_callable: Any,
    *args: Any,
    **kwargs: Any,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    try:
        async for projects in search_all_projects():

            tasks = [
                rate_limiter.paginate_with_limit(
                    project_dependent_callable, project, *args, **kwargs
                )
                for project in projects
            ]
            if not tasks:
                raise NoProjectsFoundError(
                    "Performed a search_projects action and found no accessible Projects. This may be due to unset permissions or no currently existing projects."
                )

            async for batch in stream_async_iterators_tasks(*tasks):
                yield batch
    except Exception as e:
        logger.exception(f"Error iterating over projects: {e}")
