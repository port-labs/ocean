from enum import StrEnum
from typing import Any, AsyncGenerator, Optional, cast

import httpx
from loguru import logger
from port_ocean.context.event import event
from port_ocean.utils import http_async_client
from oauth_client import OAuthClient

from integration import DynatraceResourceConfig, EntityFieldsType

# SLOs by default are not evaluated and the initial state
# at creation is being returned in the SLO list API.
# To force evaluation, we must pass the `evaluate` query parameter,
# setting it to `true`. This will return the current state of the SLOs.
# The maximum page size for the SLO list API when it is evaluated is 25.
EVALUATED_SLO_MAX_PAGE_SIZE = 25


class ResourceKey(StrEnum):
    PROBLEM = "problem"
    SLO = "slo"
    ENTITY = "entity"


class DynatraceClient:
    def __init__(
        self, host_url: str, api_key: str, oauth_client: Optional[OAuthClient] = None
    ) -> None:
        self.host = host_url.rstrip("/")
        self.host_url = f"{host_url.rstrip('/')}/api/v2"
        self.client = http_async_client
        self.client.headers.update({"Authorization": f"Api-Token {api_key}"})
        self.oauth_client = oauth_client
        self.account_management_url = "https://api.dynatrace.com/iam/v1"

    async def _get_paginated_resources_with_oauth(
        self, base_url: str, resource_key: str, params: dict[str, Any] = {}
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch paginated resources with OAuth."""
        logger.info(f"Fetching {resource_key} from {base_url} with params {params}")
        if self.oauth_client is None:
            raise ValueError("OAuth client is not initialized")
        try:
            while True:
                response = await self.oauth_client.send_request(
                    "GET", base_url, params=params
                )
                resources = response.get(resource_key, [])
                yield resources

                next_page_key = response.get("nextPageKey")
                if not next_page_key:
                    break
                params = {"nextPageKey": next_page_key}
        except httpx.HTTPError as e:
            logger.error(f"HTTP error on {base_url}: {e}")
            raise

    async def _get_paginated_resources(
        self, url: str, resource_key: str, params: dict[str, Any] = {}
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info(f"Fetching {resource_key} from {url} with params {params}")
        try:
            while True:
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                response_data = response.json()
                resources = response_data[resource_key]
                logger.info(f"Received batch with {len(resources)} {resource_key}")
                yield resources
                next_page_key = response_data.get("nextPageKey")
                if not next_page_key:
                    break
                params = {"nextPageKey": next_page_key}
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error on {url}: {e.response.status_code} - {e.response.text}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP error on {url}: {e}")
            raise

    async def get_problems(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for problems in self._get_paginated_resources(
            f"{self.host_url}/problems", "problems", {"pageSize": 200}
        ):
            yield problems

    async def get_slos(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for slos in self._get_paginated_resources(
            f"{self.host_url}/slo",
            "slo",
            {"pageSize": EVALUATED_SLO_MAX_PAGE_SIZE, "evaluate": "true"},
        ):
            yield slos

    async def _get_entities_from_type(
        self, type_: str, entity_fields: EntityFieldsType | None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        params = {
            "entitySelector": f'type("{type_}")',
            "pageSize": 100,
        }
        if entity_fields:
            params["fields"] = entity_fields
        async for entities in self._get_paginated_resources(
            f"{self.host_url}/entities",
            "entities",
            params=params,
        ):
            yield entities

    async def get_entities(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        selector = cast(DynatraceResourceConfig, event.resource_config).selector

        for entity_type in selector.entity_types:
            async for entities in self._get_entities_from_type(
                entity_type, selector.entity_fields
            ):
                yield entities

    async def get_single_problem(self, problem_id: str) -> dict[str, Any]:
        url = f"{self.host_url}/problems/{problem_id}"
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error on {url}: {e.response.status_code} - {e.response.text}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP error on {url}: {e}")
            raise

    async def get_teams(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for teams in self._get_paginated_resources(
            f"{self.host_url}/settings/objects",
            "items",
            {"schemaIds": "builtin:ownership.teams"},
        ):
            yield teams

    async def get_users(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch paginated users from the account management API."""
        url = f"{self.account_management_url}/accounts/{self.oauth_client.account_id}/users"
        async for users in self._get_paginated_resources_with_oauth(url, "items"):
            yield users

    async def get_groups(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch paginated teams from the account management API."""
        url = f"{self.account_management_url}/accounts/{self.oauth_client.account_id}/groups"
        async for groups in self._get_paginated_resources_with_oauth(url, "items"):
            yield groups

    async def healthcheck(self) -> None:
        try:
            response = await self.client.get(
                f"{self.host}/api/v1/config/clusterversion"
            )
            response.raise_for_status()
            logger.info("Dynatrace sanity check passed")
            logger.info(f"Connected to Dynatrace version {response.json()['version']}")
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Integration failed to connect to Dynatrace instance as part of sanity check due to HTTP error: {e.response.status_code} and response text: {e.response.text}"
            )
            raise
        except httpx.HTTPError:
            logger.exception(
                "Integration failed to connect to Dynatrace instance as part of sanity check due to HTTP error"
            )
            raise
