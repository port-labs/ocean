import typing
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from typing import TYPE_CHECKING, Any, Dict, Optional, Type
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.utils.cache import cache_iterator_result
from loguru import logger
from github.clients.base_client import AbstractGithubClient
from github.core.options import SingleRepositoryOptions
from github.clients.graphql_client import GithubGraphQLClient
from github.clients.rest_client import GithubRestClient
from github.helpers.constants import LIST_REPOSITORY_GQL, SINGLE_REPOSITORY_GQL
from port_ocean.context.event import event

if TYPE_CHECKING:
    from integration import GithubPortAppConfig


class RestRepositoryExporter(AbstractGithubExporter[GithubRestClient]):

    def get_required_client(self) -> Type[AbstractGithubClient]:
        return GithubRestClient

    async def get_resource[
        ExporterOptionsT: SingleRepositoryOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:

        endpoint = (
            f"{self.client.base_url}/repos/{self.client.organization}/{options['name']}"
        )
        response = await self.client.send_api_request(endpoint)
        logger.info(f"Fetched repository with identifier: {options['name']}")
        return response.json()

    @cache_iterator_result()
    async def get_paginated_resources[
        ExporterOptionsT: Any
    ](self, options: Optional[ExporterOptionsT] = None) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all repositories in the organization with pagination."""

        params: Dict[str, Any] = dict(options) if options else {}
        port_app_config = typing.cast("GithubPortAppConfig", event.port_app_config)
        params["type"] = port_app_config.repository_visibility_filter

        async for repos in self.client.send_paginated_request(
            f"{self.client.base_url}/orgs/{self.client.organization}/repos", params
        ):
            logger.info(
                f"Fetched batch of {len(repos)} repositories from organization {self.client.organization}"
            )
            yield repos


class GraphQLRepositoryExporter(AbstractGithubExporter[GithubGraphQLClient]):
    """GraphQL exporter for repositories."""

    def get_required_client(self) -> Type[AbstractGithubClient]:
        return GithubGraphQLClient

    async def get_resource[
        ExporterOptionsT: SingleRepositoryOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:

        variables = {
            "organization": self.client.organization,
            "repositoryName": options["name"],
            "first": 1,
        }
        payload = {"query": SINGLE_REPOSITORY_GQL, "variables": variables}

        response = await self.client.send_api_request(
            self.client.base_url, method="POST", json_data=payload
        )
        logger.info(f"Fetched repository with identifier: {options['name']}")

        return response.json()["data"]["organization"]["repository"]

    @cache_iterator_result()
    async def get_paginated_resources[
        ExporterOptionsT: Any
    ](self, options: Optional[ExporterOptionsT] = None) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all repositories in the organization with pagination."""

        params: Dict[str, Any] = dict(options) if options else {}
        port_app_config = typing.cast("GithubPortAppConfig", event.port_app_config)

        variables = {
            "organization": self.client.organization,
            "visibility": port_app_config.repository_visibility_filter,
            "__path": "organization.repositories",
            **params,
        }

        async for repos in self.client.send_paginated_request(
            LIST_REPOSITORY_GQL, variables
        ):
            logger.info(
                f"Fetched batch of {len(repos)} repositories from organization {self.client.organization}"
            )
            yield repos
