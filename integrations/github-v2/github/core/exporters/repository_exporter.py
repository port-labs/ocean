from github.core.exporters.abstract_exporter import (
    AbstractGithubExporter,
)
from typing import Any, cast
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.utils.cache import cache_iterator_result
from loguru import logger
from github.clients.base_client import AbstractGithubClient
from github.core.options import ListRepositoryOptions, SingleRepositoryOptions


class RepositoryExporter(AbstractGithubExporter[AbstractGithubClient]):
    async def get_resource[
        OptionT: SingleRepositoryOptions
    ](self, options: OptionT,) -> RAW_ITEM:
        endpoint = f"repos/{self.client.organization}/{options['name']}"
        response = await self.client.send_api_request(endpoint)
        logger.debug(f"Fetched repository with identifier: {options['name']}")
        return response.json()

    @cache_iterator_result()
    async def get_paginated_resources[
        OptionsT: ListRepositoryOptions
    ](self, options: OptionsT,) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all repositories in the organization with pagination."""

        params = cast(dict[str, Any], options)

        async for repos in self.client.send_paginated_request(
            f"orgs/{self.client.organization}/repos", params
        ):
            logger.info(
                f"Fetched batch of {len(repos)} repositories from organization {self.client.organization}"
            )
            yield repos
