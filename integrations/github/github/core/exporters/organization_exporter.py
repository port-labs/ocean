from loguru import logger

from github.core.options import ListOrganizationOptions
from port_ocean.utils.cache import cache_iterator_result
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.clients.http.rest_client import GithubRestClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM


class RestOrganizationExporter(AbstractGithubExporter[GithubRestClient]):
    """Exporter for GitHub organizations using REST API."""

    @cache_iterator_result()
    async def get_paginated_resources(
        self, options: ListOrganizationOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        logger.info("Fetching organizations")

        organizations = options.get("organizations")
        organizations_set = set(organizations) if organizations else None

        async for orgs in self.client.send_paginated_request(
            f"{self.client.base_url}/user/orgs", {}
        ):
            if organizations_set:
                filtered_orgs = [
                    org for org in orgs if org.get("login") in organizations_set
                ]
                logger.info(
                    f"Filtered to {len(filtered_orgs)} organizations from {len(orgs)} total"
                )
                yield filtered_orgs
            else:
                yield orgs

    async def get_resource[ExporterOptionsT: None](self, options: None) -> RAW_ITEM:
        raise NotImplementedError
