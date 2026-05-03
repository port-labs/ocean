from typing import Optional, cast

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import ListPagesOptions
from github.helpers.utils import (
    enrich_with_organization,
    enrich_with_repository,
    parse_github_options,
)
from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM


class RestPagesExporter(AbstractGithubExporter[GithubRestClient]):
    async def get_resource[ExporterOptionsT: None](
        self, options: None
    ) -> Optional[RAW_ITEM]:
        raise NotImplementedError

    async def get_paginated_resources[ExporterOptionsT: ListPagesOptions](
        self, options: ExporterOptionsT
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get the GitHub Pages configuration for a repository."""

        repo_name, organization, params = parse_github_options(dict(options))
        params.pop("repo", None)
        repo_name = cast(str, repo_name)
        endpoint = f"{self.client.base_url}/repos/{organization}/{repo_name}/pages"
        response = await self.client.send_api_request(endpoint, params)
        if not response:
            logger.debug(
                f"Skipping GitHub Pages sync for repository {repo_name} from {organization}: empty response"
            )
            return

        logger.info(
            f"Fetched GitHub Pages configuration from repository {repo_name} from {organization}"
        )

        yield [
            enrich_with_organization(
                enrich_with_repository(response, repo_name), organization
            )
        ]
