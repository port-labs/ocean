from typing import Any, cast

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.utils.cache import cache_iterator_result
from loguru import logger
from github.core.options import ListFolderOptions, SingleFolderOptions
from wcmatch import glob


class RestFolderExporter(AbstractGithubExporter[GithubRestClient]):
    _caches: dict[tuple[str, str, bool], list[dict[str, Any]]] = {}

    async def get_resource[
        ExporterOptionsT: SingleFolderOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:
        raise NotImplementedError

    @cache_iterator_result()
    async def get_paginated_resources[
        ExporterOptionsT: ListFolderOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        path = options["path"]
        branch_ref = options["branch"] or options["repo"]["default_branch"]
        repo_name = options["repo"]["name"]

        is_recursive_api_call = self._needs_recursive_search(path)
        params = {"recursive": "true"} if is_recursive_api_call else {}
        url = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/git/trees/{branch_ref}"

        if self._branch_is_cached(repo_name, branch_ref, is_recursive_api_call):
            tree = self._get_cached_tree(repo_name, branch_ref, is_recursive_api_call)
            folders = self._retrieve_relevant_tree(tree, options)
            yield folders
        else:
            async for contents in self.client.send_paginated_request(
                url, params=params
            ):
                content_cast = cast(dict[str, Any], contents)
                tree = content_cast["tree"]
                self._cache_tree(repo_name, branch_ref, is_recursive_api_call, tree)
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
            if glob.globmatch(item["path"], path, flags=glob.GLOBSTAR)
        ]

    def _branch_is_cached(
        self, repo_name: str, branch: str, is_recursive_fetch: bool
    ) -> bool:
        return (repo_name, branch, is_recursive_fetch) in self._caches

    def _get_cached_tree(
        self, repo_name: str, branch: str, is_recursive_fetch: bool
    ) -> list[dict[str, Any]]:
        return self._caches[(repo_name, branch, is_recursive_fetch)]

    def _cache_tree(
        self,
        repo_name: str,
        branch: str,
        is_recursive_fetch: bool,
        tree: list[dict[str, Any]],
    ) -> None:
        self._caches[(repo_name, branch, is_recursive_fetch)] = tree

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
