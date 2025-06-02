from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from typing import Optional
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.utils.cache import cache_iterator_result
from loguru import logger
from github.core.options import ListFolderOptions, SingleFolderOptions


class RestFolderExporter(AbstractGithubExporter[GithubRestClient]):
    async def get_resource[ExporterOptionsT: SingleFolderOptions](
        self, options: ExporterOptionsT
    ) -> RAW_ITEM:
        repo_name = options["repo"]
        folder_path = options["path"]

        endpoint = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/contents/{folder_path}"
        response = await self.client.send_api_request(endpoint)

        # If the response is a dictionary, it means the path referred to a single file or an error.
        # If it's a list, it means the path referred to a directory, and it contains its children.
        if isinstance(response, dict):
            logger.info(
                f"Fetched single item at path: {folder_path} in repository: {repo_name}"
            )
            return response
        elif isinstance(response, list):
            logger.warning(
                f"Path '{folder_path}' in repository '{repo_name}' is a directory. "
                "Cannot represent a directory as a single RAW_ITEM directly. "
                "Returning an empty dictionary. Use get_paginated_resources to list its contents."
            )
            return {}
        else:
            logger.warning(
                f"Unexpected response type for path: {folder_path} in repository: {repo_name}"
            )
            return {}

    @cache_iterator_result()
    async def get_paginated_resources[ExporterOptionsT: ListFolderOptions](
        self, options: Optional[ExporterOptionsT] = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        if not options or "repo" not in options:
            logger.error(
                "repository name is required in ListFolderOptions for Folder Exporter."
            )
            yield []
            return

        branch_ref = options["repo"]["default_branch"]
        repo_name = options["repo"]["name"]
        endpoint = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/git/trees/{branch_ref}"
        async for contents in self.client.send_paginated_request(endpoint):
            folders = [item for item in contents["tree"] if item.get("type") == "tree"]
            if folders:
                formatted = self._format_for_port(folders, repo=options["repo"])
                yield formatted
            else:
                yield []

    @staticmethod
    def _format_for_port(folders: list[dict], repo: dict | None = None) -> list[dict]:
        formatted_folders = [{"folder": folder, "repo": repo} for folder in folders]
        return formatted_folders
