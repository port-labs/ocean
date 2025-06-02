import re

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.utils.cache import cache_iterator_result
from loguru import logger
from github.core.options import ListFolderOptions, SingleFolderOptions
from github.helpers.utils import translate_glob_pattern


class RestFolderExporter(AbstractGithubExporter[GithubRestClient]):
    async def get_resource[ExporterOptionsT: SingleFolderOptions](
        self, options: ExporterOptionsT
    ) -> RAW_ITEM:
        "It is not clear to me what should be returned in a single resource."
        return {}

    @cache_iterator_result()
    async def get_paginated_resources[ExporterOptionsT: ListFolderOptions](
        self, options: ExporterOptionsT
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        path = options["path"]
        branch_ref = options["repo"]["default_branch"]
        repo_name = options["repo"]["name"]
        params = {"recursive": "true"} if self._needs_recursive_search(path) else {}
        endpoint = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/git/trees/{branch_ref}"
        async for contents in self.client.send_paginated_request(
            endpoint, params=params
        ):
            folders = self._filter_folder_contents(contents["tree"], path)
            if folders:
                formatted = self._format_for_port(folders, repo=options["repo"])
                yield formatted
            else:
                yield []

    @staticmethod
    def _format_for_port(folders: list[dict], repo: dict | None = None) -> list[dict]:
        formatted_folders = [{"folder": folder, "repo": repo} for folder in folders]
        return formatted_folders

    @staticmethod
    def _needs_recursive_search(path: str) -> bool:
        "Determines whether a give path requires recursive Github request param"
        if "**" in path and "/" in path:
            return True
        return False

    @staticmethod
    def _filter_folder_contents(folders: list[dict], path: str) -> list[dict]:
        "Get only trees (folders), and in complex paths, only file paths that match a glob pattern"
        just_trees = [item for item in folders if item.get("type") == "tree"]
        if path == "" or path == "*":
            return just_trees

        path_regex = translate_glob_pattern(path)
        return [
            item for item in just_trees if bool(re.fullmatch(path_regex, item["path"]))
        ]
