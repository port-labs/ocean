from typing import Any

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.utils.cache import cache_coroutine_result, cache_iterator_result
from loguru import logger
from github.core.options import ListFolderOptions, SingleFolderOptions
from wcmatch import glob


class RestFolderExporter(AbstractGithubExporter[GithubRestClient]):
    async def get_resource[ExporterOptionsT: SingleFolderOptions](
        self, options: ExporterOptionsT
    ) -> RAW_ITEM:
        raise NotImplementedError

    @cache_coroutine_result()
    async def _get_tree(self, url: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        tree = await self.client.send_api_request(url, params=params)
        return tree.get("tree", [])

    @cache_iterator_result()
    async def get_paginated_resources[ExporterOptionsT: ListFolderOptions](
        self, options: ExporterOptionsT
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        path = options["path"]
        branch_ref = options["branch"] or options["repo"]["default_branch"]
        repo_name = options["repo"]["name"]

        is_recursive_api_call = self._needs_recursive_search(path)
        params = {"recursive": "true"} if is_recursive_api_call else {}
        url = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/git/trees/{branch_ref}"

        tree = await self._get_tree(url, params=params)
        folders = self._retrieve_relevant_tree(tree, options)
        yield folders

    def _enrich_folder_with_repository(
        self, folders: list[dict[str, Any]], repo: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        formatted_folders = [
            {
                "folder": {**folder, "name": self._get_folder_name(folder["path"])},
                "__repository": repo,
            }
            for folder in folders
        ]
        return formatted_folders

    @staticmethod
    def _get_folder_name(folder_path: str) -> str:
        path_split = folder_path.split("/")
        name = path_split[len(path_split) - 1]
        return name

    @staticmethod
    def _needs_recursive_search(path: str) -> bool:
        "Determines whether a give path requires recursive Github request param"

        if "*" in path or "/" in path:
            return True
        return False

    @staticmethod
    def _filter_folder_contents(
        folders: list[dict[str, Any]], path: str
    ) -> list[dict[str, Any]]:
        "Get only trees (folders), and in complex paths, only file paths that match a glob pattern"

        just_trees = [item for item in folders if item.get("type") == "tree"]
        if path == "" or path == "*":
            return just_trees

        return [
            item
            for item in just_trees
            if glob.globmatch(item["path"], path, flags=glob.GLOBSTAR | glob.DOTMATCH)
        ]

    def _retrieve_relevant_tree(
        self, tree: list[dict[str, Any]], options: ListFolderOptions
    ) -> list[dict[str, Any]]:
        folders = self._filter_folder_contents(tree, options["path"])
        logger.info(f"fetched {len(folders)} folders from {options['repo']['name']}")
        if folders:
            formatted = self._enrich_folder_with_repository(
                folders, repo=options["repo"]
            )
            return formatted
        else:
            return []
