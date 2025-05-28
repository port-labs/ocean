from github.core.exporters.abstract_exporter import AbstractGithubExporter
from typing import Any, Dict, Optional
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.utils.cache import cache_iterator_result
from loguru import logger
from github.core.options import ListTagOptions, SingleTagOptions
from github.clients.rest_client import GithubRestClient


class RestTagExporter(AbstractGithubExporter[GithubRestClient]):

    async def get_resource[
        ExporterOptionsT: SingleTagOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:
        repo_name = options["repo_name"]
        tag_name = options["tag_name"]

        endpoint = (
            f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/git/refs/tags/{tag_name}"
        )
        response = await self.client.send_api_request(endpoint)
        logger.info(f"Fetched tag: {tag_name} for repo: {repo_name}")

        data = {"tag": {**response, "name": tag_name, "commit": response["object"]}, "repo": {"name": repo_name}}
        return data

    async def get_paginated_resources[
        ExporterOptionsT: ListTagOptions
    ](self, options: Optional[ExporterOptionsT] = None) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all tags in the repository with pagination."""

        params: Dict[str, Any] = dict(options) if options else {}
        repo_name = params.pop("repo_name")

        async for tags in self.client.send_paginated_request(
            f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/tags",
            params
        ):
            logger.info(
                f"Fetched batch of {len(tags)} tags from repository {repo_name}"
            )
            batch_data = [{"repo": {"name": repo_name}, "tag": tag} for tag in tags]
            yield batch_data 