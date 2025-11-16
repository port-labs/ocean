from github.core.exporters.abstract_exporter import AbstractGithubExporter
from typing import Any, Dict, cast
from github.helpers.utils import (
    enrich_with_repository,
    enrich_with_tag_name,
    enrich_with_commit,
    parse_github_options,
    enrich_with_organization,
)
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.options import ListTagOptions, SingleTagOptions
from github.clients.http.rest_client import GithubRestClient


class RestTagExporter(AbstractGithubExporter[GithubRestClient]):

    def _enrich_tag(
        self, response: Dict[str, Any], repo_name: str, tag_name: str, organization: str
    ) -> Dict[str, Any]:
        response = enrich_with_organization(
            enrich_with_repository(response, repo_name), organization
        )
        response = enrich_with_tag_name(response, tag_name)

        return enrich_with_commit(response, response["object"])

    async def get_resource[
        ExporterOptionsT: SingleTagOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:

        repo_name, organization, params = parse_github_options(dict(options))
        tag_name = params["tag_name"]

        endpoint = f"{self.client.base_url}/repos/{organization}/{repo_name}/git/refs/tags/{tag_name}"
        response = await self.client.send_api_request(endpoint)
        logger.info(
            f"Fetched tag: {tag_name} for repo: {repo_name} from {organization}"
        )

        return self._enrich_tag(response, cast(str, repo_name), tag_name, organization)

    async def get_paginated_resources[
        ExporterOptionsT: ListTagOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all tags in the repository with pagination."""

        repo_name, organization, params = parse_github_options(dict(options))

        async for tags in self.client.send_paginated_request(
            f"{self.client.base_url}/repos/{organization}/{repo_name}/tags",
            params,
        ):
            logger.info(
                f"Fetched batch of {len(tags)} tags from repository {repo_name} from {organization}"
            )
            batch_data = [
                enrich_with_organization(
                    enrich_with_repository(tag, cast(str, repo_name)), organization
                )
                for tag in tags
            ]
            yield batch_data
