from asyncio import BoundedSemaphore
from functools import partial
from typing import Any

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_independent_async_iterators,
)

from gcp_core.helpers.ratelimiter.base import MAXIMUM_CONCURRENT_REQUESTS
from gcp_core.search.resource_searches import search_all_projects


async def as_single_page(
    projects: list[dict[str, Any]],
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    yield projects


async def iterate_per_available_project(
    project_dependent_callable: Any,
    *args: Any,
    max_concurrent_projects: int = MAXIMUM_CONCURRENT_REQUESTS,
    projects: list[dict[str, Any]] | None = None,
    **kwargs: Any,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Fans out `project_dependent_callable` across every available project, across
    every page of projects.

    `projects` replaces the project source with a caller-supplied list, which is how
    an incremental sync narrows the fan-out to the projects that changed. It is a
    declared parameter rather than one of `kwargs`, because `kwargs` is forwarded
    verbatim to `project_dependent_callable`.

    A failing project doesn't stop the others: errors are deferred and raised
    together, as an `ExceptionGroup`, only after every project has finished.
    """
    semaphore = BoundedSemaphore(max_concurrent_projects)
    asset_type = kwargs.get("asset_type", "unknown")
    context = f"iterate_per_available_project[{asset_type}]"
    errors: list[Exception] = []

    if projects is not None and not projects:
        logger.debug(
            f"No project was given to search for {asset_type}, skipping the fan-out"
        )
        return

    project_pages = (
        as_single_page(projects) if projects is not None else search_all_projects()
    )

    async for project_page in project_pages:
        tasks = [
            semaphore_async_iterator(
                semaphore,
                partial(project_dependent_callable, project, *args, **kwargs),
            )
            for project in project_page
        ]
        if not tasks:
            logger.warning(
                f"Searched {len(project_page)} projects and found no accessible resources for {asset_type}. This may be due to unset permissions or no currently existing projects."
            )
            continue

        try:
            async for batch in stream_independent_async_iterators(
                *tasks, context=context
            ):
                yield batch
        except ExceptionGroup as page_errors:  # noqa: F821
            errors.extend(page_errors.exceptions)

    if errors:
        raise ExceptionGroup(  # noqa: F821
            f"{context} failed with {len(errors)} error(s)", errors
        )
