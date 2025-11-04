from collections import defaultdict
from typing import Any, List

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.utils.cache import cache_coroutine_result
from wcmatch import glob

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import (
    ListFolderOptions,
    SingleFolderOptions,
)
from github.helpers.utils import (
    IgnoredError,
    get_repos_and_branches_for_selector,
)
from integration import FolderSelector

# default key in path mapping when branch is not passed
_DEFAULT_BRANCH = "hard_to_replicate_name"


async def create_path_mapping(
    folders: list[FolderSelector],
    org_exporter: "AbstractGithubExporter[Any]",
    repo_exporter: "AbstractGithubExporter[Any]",
    repo_type: str,
) -> List[ListFolderOptions]:
    """
    Build a flat list of folder search options:
    organization -> repo_name -> [FolderSearchOptions].
    Resolves exact and glob repositories per folder selector.
    """
    repo_map: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

    logger.info(
        f"Grouping folder patterns for {len(folders)} patterns using repo_type '{repo_type}'..."
    )
    for folder_selector in folders:
        path = folder_selector.path

        async for (
            repo_name,
            branch,
            org,
            repo_obj,
        ) in get_repos_and_branches_for_selector(
            folder_selector, org_exporter, repo_exporter, repo_type
        ):
            repo_map[(org, repo_name)].append(
                {
                    "organization": org,
                    "branch": branch,
                    "path": path,
                    "repo": repo_obj,
                }
            )

    return [
        ListFolderOptions(organization=org, repo_name=repo, folders=items)
        for (org, repo), items in repo_map.items()
    ]


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
        ExporterOptionsT: List[ListFolderOptions]
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Search for folders across repositories and fetch their trees."""

        for repo_opts in options:
            organization = repo_opts["organization"]
            repo_name = repo_opts["repo_name"]
            folders_patterns = repo_opts["folders"]

            logger.debug(
                f"Processing {organization}/{repo_name} with {len(folders_patterns)} folder patterns"
            )

            for folder in folders_patterns:
                path = folder["path"]
                branch = folder.get("branch") or _DEFAULT_BRANCH
                repo = folder["repo"]
                branch_ref = (
                    branch if branch != _DEFAULT_BRANCH else repo.get("default_branch")
                )

                url = f"{self.client.base_url}/repos/{organization}/{repo_name}/git/trees/{branch_ref}"
                is_recursive_api_call = self._needs_recursive_search(path)
                tree = await self._get_tree(url, recursive=is_recursive_api_call)
                folders = self._retrieve_relevant_tree(
                    organization, tree, path=path, repo=repo
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
