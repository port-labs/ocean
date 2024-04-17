import typing
from typing import Any, AsyncIterable, Callable

import aiostream  # type: ignore
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from gcp_core.search.searches import search_all_projects


async def stream_async_iterators_tasks(
    tasks: typing.List[typing.AsyncIterable[typing.Any]],
) -> typing.AsyncIterable[typing.Any]:
    """
    Streams the results of multiple async iterators

    :param tasks: A list of async iterators
    :return: A stream of results
    """
    combine = aiostream.stream.merge(tasks[0], *tasks[1:])
    async with combine.stream() as streamer:
        async for batch_items in streamer:
            yield batch_items


async def iterate_per_available_project(
    project_dependent_callable: Callable[..., AsyncIterable[Any]],
    *args: Any,
    **kwargs: Any,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for projects in search_all_projects():
        tasks = [
            project_dependent_callable(project, *args, **kwargs) for project in projects
        ]
        async for batch in stream_async_iterators_tasks(tasks):
            yield batch
