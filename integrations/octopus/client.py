from enum import StrEnum
from typing import Any, AsyncGenerator, Optional
from loguru import logger
from port_ocean.utils.cache import cache_iterator_result
from port_ocean.utils import http_async_client
from httpx import HTTPStatusError, Timeout

PAGE_SIZE = 50
WEBHOOK_TIMEOUT = "00:00:50"
CLIENT_TIMEOUT = 60
KINDS_WITH_LIMITATION = ["deployment"]
MAX_ITEMS_LIMITATION = 100


class ObjectKind(StrEnum):
    SPACE = "space"
    PROJECT = "project"
    DEPLOYMENT = "deployment"
    RELEASE = "release"
    MACHINE = "machine"


class OctopusClient:
    def __init__(self, server_url: str, octopus_api_key: str) -> None:
        self.octopus_url = f"{server_url.rstrip('/')}/api/"
        self.api_auth_header = {"X-Octopus-ApiKey": octopus_api_key}
        self.client = http_async_client
        self.client.timeout = Timeout(CLIENT_TIMEOUT)
        self.client.headers.update(self.api_auth_header)

    async def _send_api_request(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        method: str = "GET",
    ) -> Any:
        """Send a request to the Octopus Deploy API."""
        url = f"{self.octopus_url}{endpoint}"
        response = await self.client.request(
            url=url,
            method=method,
            headers=self.api_auth_header,
            params=params,
            json=json_data,
        )
        try:
            response.raise_for_status()
        except HTTPStatusError as e:
            logger.error(
                f"Got HTTP error to url: {url} with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            raise
        return response.json()

    async def get_paginated_resources(
        self,
        kind: str,
        params: Optional[dict[str, Any]] = None,
        path_parameter: Optional[str] = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch paginated data from the Octopus Deploy API."""
        endpoint = f"{path_parameter}/{kind}s" if path_parameter else f"{kind}s"
        if params is None:
            params = {}
        params["skip"] = 0
        params["take"] = PAGE_SIZE
        page = 0
        while True:
            response = await self._send_api_request(endpoint, params=params)
            items = response.get("Items", [])
            last_page = response.get("LastPageNumber", 0)
            yield items
            if page >= last_page:
                break
            if kind in KINDS_WITH_LIMITATION and params["skip"] >= MAX_ITEMS_LIMITATION:
                logger.warning(
                    f"Reached the limit of {MAX_ITEMS_LIMITATION} {kind}s. Skipping the rest of the {kind}s."
                )
                break
            params["skip"] += PAGE_SIZE
            page += 1

    async def get_single_resource(
        self, resource_kind: str, resource_id: str, space_id: str
    ) -> dict[str, Any]:
        """Get a single resource by kind and ID."""
        return await self._send_api_request(f"{space_id}/{resource_kind}/{resource_id}")

    async def get_single_space(self, space_id: str) -> dict[str, Any]:
        """Get a single space by ID."""
        return await self._send_api_request(f"{ObjectKind.SPACE}s/{space_id}")

    @cache_iterator_result()
    async def get_all_spaces(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get all spaces in the Octopus instance."""
        async for spaces in self.get_paginated_resources(ObjectKind.SPACE):
            yield spaces

    async def _create_subscription(
        self, space_id: str, app_host: str
    ) -> dict[str, Any]:
        """Create a new subscription for a space."""
        endpoint = "subscriptions"
        subscription_data = {
            "EventNotificationSubscription": {
                "WebhookURI": f"{app_host}/integration/webhook",
                "WebhookTimeout": WEBHOOK_TIMEOUT,
            },
            "IsDisabled": False,
            "Name": f"Port Subscription - {app_host}",
            "SpaceId": space_id,
        }
        logger.info(
            f"Creating Webhook Subscription - '{subscription_data['Name']}' in '{space_id}'"
        )
        return await self._send_api_request(
            endpoint, json_data=subscription_data, method="POST"
        )

    async def create_webhook_subscription(self, app_host: str, space_id: str) -> None:
        """Create a new subscription for all spaces."""
        try:
            response = await self._create_subscription(space_id, app_host)
            if response.get("Id"):
                logger.info(
                    f"Subscription created for space '{space_id}' with ID {response['Id']}"
                )
            else:
                logger.error(f"Failed to create subscription for space '{space_id}'")
        except Exception as e:
            logger.error(f"Unexpected error for space '{space_id}': {str(e)}")

    async def get_webhook_subscriptions(
        self,
        space_id: str,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get existing subscriptions."""
        async for subscriptions in self.get_paginated_resources(
            "subscription", path_parameter=space_id
        ):
            logger.info(
                f"Retrieved {len(subscriptions)} subscriptions for space {space_id}."
            )
            yield subscriptions
