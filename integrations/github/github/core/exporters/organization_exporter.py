from typing import Any, AsyncGenerator, Dict, List
from loguru import logger

from github.core.options import ListOrganizationOptions
from github.clients.http.organization_client import OrganizationGithubClient
from port_ocean.utils.cache import cache_iterator_result


class RestOrganizationExporter:
    """Exporter for GitHub organizations using REST API."""

    def __init__(self, client: OrganizationGithubClient) -> None:
        self.client = client

    @cache_iterator_result()
    async def get_paginated_resources(
        self, options: ListOrganizationOptions
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
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
