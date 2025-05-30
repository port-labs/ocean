from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from typing import Optional
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.utils.cache import cache_iterator_result
from loguru import logger
from github.core.options import ListFolderOptions, SingleFolderOptions


class RestFolderExporter(AbstractGithubExporter[GithubRestClient]):
    async def get_resource[
        ExporterOptionsT: SingleFolderOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:
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
    async def get_paginated_resources[
        ExporterOptionsT: ListFolderOptions
    ](self, options: Optional[ExporterOptionsT] = None) -> ASYNC_GENERATOR_RESYNC_TYPE:
        if not options or "repo" not in options:
            logger.error(
                "repository name is required in ListFolderOptions for Folder Exporter."
            )
            yield []
            return

        repo_name = options["repo"]
        base_path = options.get("path", "")  # Defaults to root of the repository

        endpoint = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/contents/{base_path}"
        async for contents in self.client.send_paginated_request(endpoint):
            if not isinstance(contents, list):
                if isinstance(contents, dict) and contents.get("type") == "file":
                    logger.info(
                        f"Path '{base_path}' in repository '{repo_name}' is a file. No folders to yield."
                    )
                else:
                    logger.warning(
                        f"Unexpected response type for path: {base_path} in repository: {repo_name}. "
                        f"Expected list or file, got {type(contents)}. Skipping."
                    )
                yield []
                return

            folders = [item for item in contents if item.get("type") == "dir"]
            if folders:
                yield folders
            else:
                yield []
