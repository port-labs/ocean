from collections import defaultdict
from typing import Any, DefaultDict

from loguru import logger
from github.core.exporters.file_exporter.utils import deep_dict
from github.clients.utils import get_mono_repo_organization
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.utils.cache import cache_coroutine_result
from wcmatch import glob

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import ListFolderOptions, SingleFolderOptions
from github.helpers.utils import IgnoredError, search_for_repositories
from integration import FolderSelector

# default key in path mapping when branch is not passed
_DEFAULT_BRANCH = "hard_to_replicate_name"


def create_path_mapping(
    folder_patterns: list[FolderSelector],
) -> dict[str, dict[str, dict[str, list[str]]]]:
    """
    Create a mapping of repository names to branch names to folder paths.
    """
    pattern_by_org_repo_branch: DefaultDict[
        str, DefaultDict[str, DefaultDict[str, list[str]]]
    ] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for pattern in folder_patterns:
        organization = get_mono_repo_organization(pattern.organization)
        path = pattern.path
        for repo in pattern.repos:
            repo_name = repo.name
            repo_branch = repo.branch or _DEFAULT_BRANCH
            pattern_by_org_repo_branch[organization][repo_name][repo_branch].append(
                path
            )

    return deep_dict(pattern_by_org_repo_branch)


class RestFolderExporter(AbstractGithubExporter[GithubRestClient]):
    _IGNORED_ERRORS = [
        IgnoredError(status=409, message="empty repository"),
    ]

    async def get_resource[
        ExporterOptionsT: SingleFolderOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:
        raise NotImplementedError

    @cache_coroutine_result()
    async def _get_tree(self, url: str, recursive: bool) -> list[dict[str, Any]]:
        logger.info("Fetching repository tree")
        params = {"recursive": "true"} if recursive else {}
        tree = await self.client.send_api_request(
            url, params=params, ignored_errors=self._IGNORED_ERRORS
        )
        return tree.get("tree", [])

    async def get_paginated_resources[
        ExporterOptionsT: ListFolderOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        repo_mapping = options["repo_mapping"]

        for organization, repos_by_org in repo_mapping.items():
            repos = repos_by_org.keys()

            async for search_result in search_for_repositories(
                self.client, organization, repos
            ):
                for repository in search_result:
                    repo_name = repository["name"]
                    repo_map = repos_by_org.get(repo_name)
                    if not repo_map:
                        continue

                    for branch, paths in repo_map.items():
                        for path in paths:
                            branch_ref = (
                                branch
                                if branch != _DEFAULT_BRANCH
                                else repository["default_branch"]
                            )
                            url = f"{self.client.base_url}/repos/{organization}/{repo_name}/git/trees/{branch_ref}"

                            is_recursive_api_call = self._needs_recursive_search(path)
                            tree = await self._get_tree(
                                url, recursive=is_recursive_api_call
                            )
                            folders = self._retrieve_relevant_tree(
                                organization, tree, path=path, repo=repository
                            )
                            if folders:
                                yield folders

    def _retrieve_relevant_tree(
        self,
        organization: str,
        tree: list[dict[str, Any]],
        path: str,
        repo: dict[str, Any],
    ) -> list[dict[str, Any]]:
        folders = self._filter_folder_contents(tree, path)
        logger.info(f"fetched {len(folders)} folders from {repo['name']}")
        if folders:
            formatted = self._enrich_folder_with_repository(
                organization, folders, repo=repo
            )
            return formatted
        else:
            return []

    def _enrich_folder_with_repository(
        self,
        organization: str,
        folders: list[dict[str, Any]],
        repo: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        formatted_folders = [
            {
                "folder": folder,
                "__repository": repo,
                "__organization": organization,
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
