from collections import defaultdict
from typing import Any, Generator

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.utils.cache import cache_coroutine_result
from loguru import logger
from github.core.options import ListFolderOptions, SingleFolderOptions
from github.helpers.utils import IgnoredError
from wcmatch import glob

from integration import FolderSelector


def create_pattern_mapping(
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
            pattern_by_repo_branch[repo.name][repo.branch or "default"].append(p)
    return {repo: dict(branches) for repo, branches in pattern_by_repo_branch.items()}


def create_search_params(
    repos: list[str], max_operators: int = 5
) -> Generator[str, None, None]:
    """Create search query strings that fits into Github search string limitations.

    Limitations:
        - A search query can be up to 256 characters.
        - A query can contain a maximum of 5 `OR` operators.

    """
    if not repos:
        yield ""
        return

    max_repos_in_query = max_operators + 1
    max_search_string_len = 256

    chunk: list[str] = []
    for repo in repos:
        new_chunk = chunk + [repo]
        search_string = "OR".join([f"{r}+in+name" for r in new_chunk])

        if (
            len(new_chunk) > max_repos_in_query
            or len(search_string) > max_search_string_len
        ):
            if not chunk:
                # A single repo name is too long to ever fit in a search query
                # Ai! I don't want to raise an exeception in this case, let's instead add a log, yield an empty string, then return, also update test case to match
                raise ValueError(
                    f"Repository name '{repo}' is too long to fit in a search query."
                )

            yield "OR".join([f"{r}+in+name" for r in chunk])
            chunk = [repo]
        else:
            chunk = new_chunk

    if chunk:
        yield "OR".join([f"{r}+in+name" for r in chunk])


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
        path = options["path"]
        branch_ref = options.get("branch") or options["repo"]["default_branch"]
        repo_name = options["repo"]["name"]

        is_recursive_api_call = self._needs_recursive_search(path)
        url = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/git/trees/{branch_ref}"

        tree = await self._get_tree(url, recursive=is_recursive_api_call)
        folders = self._retrieve_relevant_tree(tree, options)
        yield folders

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

    async def _search_for_repositories(
        self, repos: list[str], max_operators: int = 5
    ) -> list[dict[str, Any]]:
        search_params = "OR".join([f"{repo}+in+name" for repo in repos])
        query = f"org:{self.client.organization} {search_params} forks:true"
        pass
