from typing import Any, List, Optional

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
from github.helpers.changed_paths import ancestor_dirs, changed_paths_since
from github.helpers.utils import IgnoredError, matches_glob_pattern


class RestFolderExporter(AbstractGithubExporter[GithubRestClient]):
    _IGNORED_ERRORS = [
        IgnoredError(status=409, message="empty repository"),
    ]

    async def get_resource[ExporterOptionsT: SingleFolderOptions](
        self, options: ExporterOptionsT
    ) -> Optional[RAW_ITEM]:
        raise NotImplementedError

    @cache_coroutine_result()
    async def _get_tree(self, url: str, recursive: bool) -> list[dict[str, Any]]:
        logger.info("Fetching repository tree")
        params = {"recursive": "true"} if recursive else {}
        tree = await self.client.send_api_request(
            url, params=params, ignored_errors=self._IGNORED_ERRORS
        )
        return tree.get("tree", [])

    async def get_paginated_resources[ExporterOptionsT: List[ListFolderOptions]](
        self, options: ExporterOptionsT
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Search for folders across repositories and fetch their trees.

        A repository's ``changed_since`` limits it to folders containing a path
        changed since then.
        """

        for repo_opts in options:
            organization = repo_opts["organization"]
            repo_name = repo_opts["repo_name"]
            folders_patterns = repo_opts["folders"]
            changed_since = repo_opts.get("changed_since")

            logger.debug(
                f"Processing {organization}/{repo_name} with {len(folders_patterns)} folder patterns"
            )

            for folder in folders_patterns:
                path = folder["path"]
                repo = folder["repo"]
                branch = folder.get("branch") or repo["default_branch"]

                changed_paths = await changed_paths_since(
                    self.client, organization, repo_name, branch, changed_since
                )
                url = f"{self.client.base_url}/repos/{organization}/{repo_name}/git/trees/{branch}"
                is_recursive_api_call = self._needs_recursive_search(path)
                tree = await self._get_tree(url, recursive=is_recursive_api_call)
                folders = self._retrieve_relevant_tree(
                    organization,
                    tree,
                    path=path,
                    repo=repo,
                    branch=branch,
                    changed_paths=changed_paths,
                )
                if folders:
                    yield folders

    def _retrieve_relevant_tree(
        self,
        organization: str,
        tree: list[dict[str, Any]],
        path: str,
        repo: dict[str, Any],
        branch: str,
        changed_paths: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """Folders matching ``path``; with known ``changed_paths``, only those containing one."""
        folders = self._filter_folder_contents(tree, path)
        if changed_paths is not None:
            changed_dirs = ancestor_dirs(changed_paths)
            folders = [folder for folder in folders if folder["path"] in changed_dirs]
        logger.info(f"fetched {len(folders)} folders from {repo['name']}")
        if folders:
            formatted = self._enrich_folder_with_repository(
                organization, folders, repo=repo, branch=branch
            )
            return formatted
        else:
            return []

    def _enrich_folder_with_repository(
        self,
        organization: str,
        folders: list[dict[str, Any]],
        repo: dict[str, Any] | None = None,
        branch: str | None = None,
    ) -> list[dict[str, Any]]:
        formatted_folders = [
            {
                "folder": folder,
                "__repository": repo,
                "__organization": organization,
                "__branch": branch,
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
            if matches_glob_pattern(item["path"], path, flags=glob.DOTMATCH)
        ]
