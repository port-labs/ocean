from typing import Any, Optional, cast

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import ListPagesOptions, SinglePagesOptions
from github.helpers.utils import (
    enrich_with_organization,
    enrich_with_repository,
    parse_github_options,
)
from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM


class RestPagesExporter(AbstractGithubExporter[GithubRestClient]):
    async def get_resource[ExporterOptionsT: SinglePagesOptions](
        self, options: ExporterOptionsT
    ) -> Optional[RAW_ITEM]:
        """Get the GitHub Pages configuration for a repository."""

        repo_name, organization, params = parse_github_options(dict(options))
        params.pop("repo", None)
        response = await self._fetch_pages(cast(str, repo_name), organization, params)
        if not response:
            logger.debug(
                f"Skipping GitHub Pages sync for repository {repo_name} from {organization}: empty response"
            )
            return None

        logger.info(
            f"Fetched GitHub Pages configuration from repository {repo_name} from {organization}"
        )

        return self._enrich_pages(response, cast(str, repo_name), organization)

    async def get_paginated_resources[ExporterOptionsT: ListPagesOptions](
        self, options: ExporterOptionsT
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get the GitHub Pages configuration for a repository."""

        repo_name, organization, params = parse_github_options(dict(options))
        params.pop("repo", None)
        response = await self._fetch_pages(cast(str, repo_name), organization, params)
        if not response:
            logger.debug(
                f"Skipping GitHub Pages sync for repository {repo_name} from {organization}: empty response"
            )
            return

        logger.info(
            f"Fetched GitHub Pages configuration from repository {repo_name} from {organization}"
        )

        yield [self._enrich_pages(response, cast(str, repo_name), organization)]

    async def _fetch_pages(
        self, repo_name: str, organization: str, params: dict[str, Any]
    ) -> RAW_ITEM:
        endpoint = f"{self.client.base_url}/repos/{organization}/{repo_name}/pages"
        return await self.client.send_api_request(endpoint, params)

    def _enrich_pages(
        self, response: RAW_ITEM, repo_name: str, organization: str
    ) -> RAW_ITEM:
        return enrich_with_organization(
            enrich_with_repository(response, repo_name), organization
        )
