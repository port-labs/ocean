import asyncio
import json
from functools import partial
from typing import Any, List, Optional

from loguru import logger

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.exporters.file_exporter.core import RestFileExporter
from github.core.exporters.plugin_exporter.utils import (
    PLUGIN_DIRECTORY_PREFIXES,
    PluginProvider,
    build_plugin_raw_item,
    find_plugin_roots,
    normalize_plugin,
)
from github.core.options import (
    FileContentOptions,
    ListPluginOptions,
    PluginRepositoryOptions,
)
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_async_iterators_tasks,
)

# Reading a repository's full git tree is heavy, so cap how many repositories
# are scanned at once regardless of how many are handed to the exporter.
MAX_CONCURRENT_PLUGIN_REPOS = 10


class PluginExporter(AbstractGithubExporter[GithubRestClient]):
    """Detects agent plugin manifests and emits one normalized plugin per plugin root."""

    def __init__(
        self,
        client: GithubRestClient,
        providers: List[PluginProvider],
        max_depth: Optional[int] = None,
    ) -> None:
        super().__init__(client)
        self.providers = providers
        self.max_depth = max_depth
        self._file_exporter = RestFileExporter(client)

    async def get_resource[ExporterOptionsT: PluginRepositoryOptions](  # type: ignore[override]
        self, options: ExporterOptionsT
    ) -> list[RAW_ITEM]:
        """Build the plugin raw items for every plugin root in a repository."""
        roots, _ = await self.get_plugin_roots(options)
        items = [
            item
            for root, paths in sorted(roots.items())
            if (item := await self.build_plugin_item(options, root, paths))
        ]
        logger.info(
            f"Found {len(items)} plugin(s) in "
            f"{options['organization']}/{options['repository']['name']}"
        )
        return items

    async def get_plugin_roots(
        self, options: PluginRepositoryOptions
    ) -> tuple[dict[str, dict[PluginProvider, set[str]]], bool]:
        """Plugin roots of a repository (from one tree fetch) and tree truncation."""
        organization, repo_name = options["organization"], options["repository"]["name"]
        tree, truncated = await self._file_exporter.get_tree_recursive(
            organization, repo_name, options["branch"]
        )
        if truncated:
            logger.warning(
                f"Git tree of {organization}/{repo_name} was truncated; "
                "plugin detection may be incomplete"
            )
        blobs = {
            entry["path"]
            for entry in tree or []
            if entry.get("type") == "blob" and isinstance(entry.get("path"), str)
        }
        return find_plugin_roots(blobs, self.providers, self.max_depth), truncated

    async def build_plugin_item(
        self,
        options: PluginRepositoryOptions,
        root: str,
        paths: dict[PluginProvider, set[str]],
    ) -> Optional[RAW_ITEM]:
        """Raw item for one plugin root, or None when it does not describe a plugin."""
        organization = options["organization"]
        repository = options["repository"]
        branch = options["branch"]
        directory_supports = {p for p in paths if p in PLUGIN_DIRECTORY_PREFIXES}
        manifest_paths = sorted(
            path
            for provider, provider_paths in paths.items()
            if provider not in directory_supports
            for path in provider_paths
        )
        manifests = await self._fetch_manifests(
            organization, repository["name"], branch, root, manifest_paths
        )
        plugin = normalize_plugin(
            repository=repository,
            manifests=manifests,
            providers=self.providers,
            path=root,
            directory_supports=directory_supports,
        )
        if not plugin:
            return None
        return build_plugin_raw_item(
            plugin=plugin,
            repository=repository,
            branch=branch,
            organization=organization,
        )

    async def get_paginated_resources[ExporterOptionsT: ListPluginOptions](
        self, options: ExporterOptionsT
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_PLUGIN_REPOS)
        tasks = [
            semaphore_async_iterator(
                semaphore, partial(self._iterate_repository_plugin, repo_options)
            )
            for repo_options in options["repositories"]
        ]

        async for batch in stream_async_iterators_tasks(*tasks):
            yield batch

    async def is_tree_truncated(
        self, organization: str, repo_name: str, branch: str
    ) -> bool:
        """Whether GitHub truncated the git tree used for plugin detection."""
        _, is_truncated = await self._file_exporter.get_tree_recursive(
            organization, repo_name, branch
        )
        return is_truncated

    async def _iterate_repository_plugin(
        self, options: PluginRepositoryOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        try:
            plugin_items = await self.get_resource(options)
        except Exception as exc:
            logger.warning(
                f"Failed to process plugin manifests for "
                f"{options['repository'].get('name')}: {exc}"
            )
            return

        if plugin_items:
            yield plugin_items

    async def _fetch_manifests(
        self,
        organization: str,
        repo_name: str,
        branch: str,
        root: str,
        paths: List[str],
    ) -> dict[str, Any]:
        """Parsed manifests keyed by marker path relative to the plugin root."""
        manifests: dict[str, Any] = {}
        for path in paths:
            file_data = await self._file_exporter.get_resource(
                FileContentOptions(
                    organization=organization,
                    repo_name=repo_name,
                    file_path=path,
                    branch=branch,
                )
            )
            if not file_data:
                continue
            content = file_data.get("content")
            if not isinstance(content, str):
                continue
            try:
                manifests[path.removeprefix(root).lstrip("/")] = json.loads(content)
            except json.JSONDecodeError as exc:
                logger.warning(f"Invalid JSON in plugin manifest {path}: {exc}")
        return manifests
