from typing import Any

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import stream_async_iterators_tasks

from gcp_core.errors import NoProjectsFoundError
from gcp_core.search.resource_searches import search_all_projects


async def iterate_per_available_project(
    project_dependent_callable: Any,
    *args: Any,
    **kwargs: Any,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    try:
        async for projects in search_all_projects():
            tasks = [
                project_dependent_callable(project, *args, **kwargs)
                for project in projects
            ]
            async for batch in stream_async_iterators_tasks(*tasks):
                yield batch
    except StopAsyncIteration:
        raise NoProjectsFoundError(
            "Performed a search_projects actions, and found no accessable Projects. This may be due to unset permissions or no current existing projects."
        )
