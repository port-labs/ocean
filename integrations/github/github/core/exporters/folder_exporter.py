from collections import defaultdict
from typing import Any

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.utils.cache import cache_coroutine_result
from wcmatch import glob

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import ListFolderOptions, SingleFolderOptions
from github.helpers.utils import IgnoredError, search_for_repositories
from integration import FolderSelector

_DEFAULT_BRANCH = "hard_to_replicate_name"


def create_path_mapping(
    folder_patterns: list[FolderSelector],
) -> dict[str, dict[str, list[str]]]:
    """
    Create a mapping of repository names to branch names to folder paths.
    """
    pattern_by_repo_branch: dict[str, dict[str, list[str]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for pattern in folder_patterns:
        p = pattern.path
        for repo in pattern.repos:
            pattern_by_repo_branch[repo.name][repo.branch or _DEFAULT_BRANCH].append(p)
    return {repo: dict(branches) for repo, branches in pattern_by_repo_branch.items()}


class RestFolderExporter(AbstractGithubExporter[GithubRestClient]):
    _IGNORED_ERRORS = [
        IgnoredError(status=409, message="empty repository"),
    ]

    async def get_resource[ExporterOptionsT: SingleFolderOptions](
        self, options: ExporterOptionsT
    ) -> RAW_ITEM:
        raise NotImplementedError

    @cache_coroutine_result()
    async def _get_tree(self, url: str, recursive: bool) -> list[dict[str, Any]]:
        logger.info("Fetching repository tree")
        params = {"recursive": "true"} if recursive else {}
        tree = await self.client.send_api_request(
            url, params=params, ignored_errors=self._IGNORED_ERRORS
        )
        return tree.get("tree", [])

    async def get_paginated_resources[ExporterOptionsT: ListFolderOptions](
        self, options: ExporterOptionsT
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        repo_mapping = options["repo_mapping"]
        repos = repo_mapping.keys()

        async for search_result in search_for_repositories(self.client, repos):
            for repository in search_result:
                repo_name = repository["name"]
                repo_map = repo_mapping.get(repo_name)
                if not repo_map:
                    continue

                for branch, paths in repo_map.items():
                    for path in paths:
                        branch_ref = (
                            branch
                            if branch != _DEFAULT_BRANCH
                            else repository["default_branch"]
                        )
                        url = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/git/trees/{branch_ref}"

                        is_recursive_api_call = self._needs_recursive_search(path)
                        tree = await self._get_tree(
                            url, recursive=is_recursive_api_call
                        )
                        folders = self._retrieve_relevant_tree(
                            tree, path=path, repo=repository
                        )
                        if folders:
                            yield folders

    def _retrieve_relevant_tree(
        self, tree: list[dict[str, Any]], path: str, repo: dict[str, Any]
    ) -> list[dict[str, Any]]:
        folders = self._filter_folder_contents(tree, path)
        logger.info(f"fetched {len(folders)} folders from {repo['name']}")
        if folders:
            formatted = self._enrich_folder_with_repository(folders, repo=repo)
            return formatted
        else:
            return []

    def _enrich_folder_with_repository(
        self, folders: list[dict[str, Any]], repo: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        formatted_folders = [
            {
                "folder": folder,
                "__repository": repo,
            }
            for folder in folders
        ]
        return formatted_folders

    @staticmethod
    def _needs_recursive_search(path: str) -> bool:
        "Determines whether a give path requires recursive Github request param. one glob star or empty path doesn't require recursive search"

        if path == "" or path == "*":
            return False

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
