from typing import Any

from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import ListRepositoryOptions
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


async def iter_repositories(
    repo_exporter: AbstractGithubExporter[Any], options: ListRepositoryOptions
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """List the repositories matching *options*.

    With both ``pushed_since`` and ``search_params``, the pushed repositories come
    from the live repository list, and search only decides which of them match the
    query: search's ``pushed:`` qualifier runs on a lagging index and misses
    recent pushes.
    """
    pushed_since = options.get("pushed_since")
    search_params = options.get("search_params")
    if pushed_since is None or search_params is None:
        async for repositories in repo_exporter.get_paginated_resources(options):
            yield repositories
        return

    pushed_options = ListRepositoryOptions(**{**options, "search_params": None})
    search_options = ListRepositoryOptions(**{**options, "pushed_since": None})
    matching_names: set[str] | None = None

    async for repositories in repo_exporter.get_paginated_resources(pushed_options):
        if matching_names is None:
            matching_names = {
                repo["name"]
                async for batch in repo_exporter.get_paginated_resources(search_options)
                for repo in batch
            }
        repositories = [repo for repo in repositories if repo["name"] in matching_names]
        if repositories:
            yield repositories
