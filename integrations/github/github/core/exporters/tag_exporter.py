from github.core.exporters.abstract_exporter import AbstractGithubExporter
from typing import Any, Dict
from github.helpers.utils import enrich_with_repository
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.options import ListTagOptions, SingleTagOptions
from github.clients.http.rest_client import GithubRestClient


class RestTagExporter(AbstractGithubExporter[GithubRestClient]):

    def _enrich_tag(
        self, response: Dict[str, Any], repo_name: str, tag_name: str
    ) -> Dict[str, Any]:
        enriched_tag = enrich_with_repository(response, repo_name)
        return {**enriched_tag, "name": tag_name, "commit": response["object"]}

    async def get_resource[
        ExporterOptionsT: SingleTagOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:
        repo_name = options["repo_name"]
        tag_name = options["tag_name"]

        endpoint = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/git/refs/tags/{tag_name}"
        response = await self.client.send_api_request(endpoint)
        logger.info(f"Fetched tag: {tag_name} for repo: {repo_name}")

        return self._enrich_tag(response, repo_name, tag_name)

    async def get_paginated_resources[
        ExporterOptionsT: ListTagOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all tags in the repository with pagination."""

        params = dict(options)
        repo_name = str(params.pop("repo_name"))

        async for tags in self.client.send_paginated_request(
            f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/tags",
            params,
        ):
            logger.info(
                f"Fetched batch of {len(tags)} tags from repository {repo_name}"
            )
            batch_data = [enrich_with_repository(tag, repo_name) for tag in tags]
            yield batch_data
