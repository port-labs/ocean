import asyncio
import json
from dataclasses import dataclass
from typing import Any, List, Optional

from loguru import logger

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.exporters.file_exporter.core import RestFileExporter
from github.core.exporters.plugin_exporter.utils import (
    PluginProvider,
    all_manifest_paths,
    detect_directory_providers,
    normalize_plugin,
)
from github.core.options import FileContentOptions
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM


@dataclass(frozen=True)
class PluginBuildResult:
    plugin_item: Optional[dict[str, Any]]
    tree_truncated: bool = False


class PluginExporter(AbstractGithubExporter[GithubRestClient]):
    """Detects agent plugin manifests and emits one normalized plugin per repo."""

    def __init__(self, client: GithubRestClient) -> None:
        super().__init__(client)
        self._file_exporter = RestFileExporter(client)

    async def get_resource(self, options: Any) -> RAW_ITEM:
        raise NotImplementedError("PluginExporter does not support get_resource")

    def get_paginated_resources(self, options: Any) -> ASYNC_GENERATOR_RESYNC_TYPE:
        raise NotImplementedError("Use get_paginated_plugins")

    async def get_paginated_plugins(
        self,
        *,
        organization: str,
        repositories: List[tuple[dict[str, Any], str]],
        providers: List[PluginProvider],
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        # Callers (see resync_plugins) already chunk `repositories` to
        # MAX_CONCURRENT_REPOS, so fetching each repo's tree concurrently here
        # keeps plugin resync in line with the org's other per-repo resyncs
        # instead of scanning repos one at a time.
        manifest_paths = set(all_manifest_paths(providers))
        results = await asyncio.gather(
            *(
                self._build_plugin_item(
                    organization=organization,
                    repository=repo,
                    branch=branch,
                    manifest_paths=manifest_paths,
                    providers=providers,
                )
                for repo, branch in repositories
            )
        )
        batch = [item for item in results if item]
        if batch:
            yield batch

    async def _build_plugin_item(
        self,
        *,
        organization: str,
        repository: dict[str, Any],
        branch: str,
        manifest_paths: set[str],
        providers: List[PluginProvider],
    ) -> Optional[dict[str, Any]]:
        try:
            result = await self.build_plugin_for_repo(
                organization=organization,
                repository=repository,
                branch=branch,
                manifest_paths=manifest_paths,
                providers=providers,
            )
        except Exception as exc:
            logger.warning(
                f"Failed to process plugin manifests for {repository.get('name')}: {exc}"
            )
            return None
        return result.plugin_item

    async def build_plugin_for_repo(
        self,
        *,
        organization: str,
        repository: dict[str, Any],
        branch: str,
        manifest_paths: set[str],
        providers: List[PluginProvider],
    ) -> PluginBuildResult:
        repo_name = repository["name"]
        tree, truncated = await self._file_exporter.get_tree_recursive_meta(
            organization, repo_name, branch
        )
        if not tree:
            return PluginBuildResult(plugin_item=None, tree_truncated=truncated)

        tree_paths = {
            entry["path"]
            for entry in tree
            if entry.get("path") and entry.get("type") in ("blob", "tree")
        }
        directory_supports = detect_directory_providers(tree_paths, providers)
        present = sorted(manifest_paths & tree_paths)
        if not present and not directory_supports:
            return PluginBuildResult(plugin_item=None, tree_truncated=truncated)

        manifests: dict[str, Any] = {}
        for path in present:
            file_data = await self._file_exporter.get_resource(
                FileContentOptions(
                    organization=organization,
                    repo_name=repo_name,
                    file_path=path,
                    branch=branch,
                )
            )
            if not file_data or file_data.get("content") is None:
                continue
            content = file_data["content"]
            if not isinstance(content, str):
                continue
            try:
                manifests[path] = json.loads(content)
            except json.JSONDecodeError as exc:
                logger.warning(f"Invalid JSON in plugin manifest {path}: {exc}")

        if not manifests and not directory_supports:
            return PluginBuildResult(plugin_item=None, tree_truncated=truncated)

        plugin = normalize_plugin(
            repository=repository,
            manifests=manifests,
            providers=providers,
            directory_supports=directory_supports,
        )
        if not plugin:
            return PluginBuildResult(plugin_item=None, tree_truncated=truncated)
        return PluginBuildResult(
            plugin_item={
                "plugin": plugin,
                "repository": repository,
                "branch": branch,
                "organization": organization,
            },
            tree_truncated=truncated,
        )
