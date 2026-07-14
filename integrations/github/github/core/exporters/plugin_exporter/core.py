import json
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


class PluginExporter(AbstractGithubExporter[GithubRestClient]):
    """Detects agent plugin manifests and emits one normalized plugin per repo."""

    def __init__(self, client: GithubRestClient) -> None:
        super().__init__(client)
        self._file_exporter = RestFileExporter(client)

    async def get_resource(self, options: Any) -> RAW_ITEM:
        raise NotImplementedError("PluginExporter does not support get_resource")

    async def get_paginated_resources(self, options: Any) -> ASYNC_GENERATOR_RESYNC_TYPE:
        raise NotImplementedError("Use get_paginated_plugins")

    async def get_paginated_plugins(
        self,
        *,
        organization: str,
        repositories: List[dict[str, Any]],
        providers: List[PluginProvider],
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        manifest_paths = set(all_manifest_paths(providers))
        batch: list[dict[str, Any]] = []

        for repo in repositories:
            repo_name = repo["name"]
            branch = repo.get("default_branch") or "main"
            try:
                plugin_item = await self.build_plugin_for_repo(
                    organization=organization,
                    repository=repo,
                    branch=branch,
                    manifest_paths=manifest_paths,
                    providers=providers,
                )
            except Exception as exc:
                logger.warning(
                    f"Failed to process plugin manifests for "
                    f"{organization}/{repo_name}: {exc}"
                )
                continue

            if plugin_item:
                batch.append(plugin_item)

            if len(batch) >= 25:
                yield batch
                batch = []

        if batch:
            yield batch

    async def build_plugin_for_repo(
        self,
        *,
        organization: str,
        repository: dict[str, Any],
        branch: str,
        manifest_paths: set[str],
        providers: List[PluginProvider],
    ) -> Optional[dict[str, Any]]:
        repo_name = repository["name"]
        tree = await self._file_exporter.get_tree_recursive(
            organization, repo_name, branch
        )
        if not tree:
            return None

        tree_paths = {
            entry["path"]
            for entry in tree
            if entry.get("path") and entry.get("type") in ("blob", "tree")
        }
        directory_supports = detect_directory_providers(tree_paths, providers)
        present = sorted(manifest_paths & tree_paths)
        if not present and not directory_supports:
            return None

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
                logger.warning(
                    f"Invalid JSON in plugin manifest "
                    f"{organization}/{repo_name}/{path}: {exc}"
                )

        if not manifests and not directory_supports:
            return None

        plugin = normalize_plugin(
            repository=repository,
            manifests=manifests,
            providers=providers,
            directory_supports=directory_supports,
        )
        if not plugin:
            return None
        return {
            "plugin": plugin,
            "repository": repository,
            "branch": branch,
            "organization": organization,
        }
