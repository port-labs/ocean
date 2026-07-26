import asyncio
import json
from functools import partial
from typing import Any, List, Optional

from loguru import logger

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.exporters.file_exporter.core import RestFileExporter
from github.core.exporters.plugin_exporter.utils import (
    Plugin,
    PluginProvider,
    all_manifest_paths,
    build_plugin_raw_item,
    detect_directory_providers,
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
    """Detects agent plugin manifests and emits one normalized plugin per repo."""

    def __init__(
        self, client: GithubRestClient, providers: List[PluginProvider]
    ) -> None:
        super().__init__(client)
        self.providers = providers
        self._manifest_paths = set(all_manifest_paths(providers))
        self._file_exporter = RestFileExporter(client)

    async def get_resource[ExporterOptionsT: PluginRepositoryOptions](
        self, options: ExporterOptionsT
    ) -> Optional[RAW_ITEM]:
        """Build the plugin raw item for a single repository, if it is one."""
        organization = options["organization"]
        repository = options["repository"]
        branch = options["branch"]

        plugin = await self._build_plugin_for_repo(organization, repository, branch)
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
            plugin_item = await self.get_resource(options)
        except Exception as exc:
            logger.warning(
                f"Failed to process plugin manifests for "
                f"{options['repository'].get('name')}: {exc}"
            )
            return

        if plugin_item:
            yield [plugin_item]

    async def _build_plugin_for_repo(
        self, organization: str, repository: dict[str, Any], branch: str
    ) -> Optional[Plugin]:
        repo_name = repository["name"]
        tree, _ = await self._file_exporter.get_tree_recursive(
            organization, repo_name, branch
        )
        if not tree:
            return None

        tree_paths = {
            entry["path"]
            for entry in tree
            if entry.get("path") and entry.get("type") in ("blob", "tree")
        }
        directory_supports = detect_directory_providers(tree_paths, self.providers)
        present = sorted(self._manifest_paths & tree_paths)
        if not present and not directory_supports:
            return None

        manifests = await self._fetch_manifests(
            organization, repo_name, branch, present
        )
        if not manifests and not directory_supports:
            return None

        return normalize_plugin(
            repository=repository,
            manifests=manifests,
            providers=self.providers,
            directory_supports=directory_supports,
        )

    async def _fetch_manifests(
        self, organization: str, repo_name: str, branch: str, paths: List[str]
    ) -> dict[str, Any]:
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
                manifests[path] = json.loads(content)
            except json.JSONDecodeError as exc:
                logger.warning(f"Invalid JSON in plugin manifest {path}: {exc}")
        return manifests
