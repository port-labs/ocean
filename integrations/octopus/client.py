from typing import Any, AsyncGenerator, Optional
from loguru import logger
from port_ocean.utils import http_async_client
from httpx import HTTPStatusError, Timeout

PAGE_SIZE = 50  # Number of items to fetch per page


class OctopusClient:
    def __init__(self, octopus_api_key: str, octopus_url: str) -> None:
        self.octopus_url = f"{octopus_url.rstrip('/')}/api/"
        self.octopus_api_key = octopus_api_key
        self.api_auth_header = {"X-Octopus-ApiKey": self.octopus_api_key}
        self.client = http_async_client
        self.client.timeout = Timeout(60)
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
        logger.warning(f"Response: {response.json()}")
        return response.json()

    async def _get_paginated_objects(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch paginated data from the Octopus Deploy API."""
        if params is None:
            params = {}
        params["skip"] = 0
        params["take"] = PAGE_SIZE
        while True:
            logger.debug(f"Fetching data from {endpoint} with params {params}")
            response = await self._send_api_request(endpoint, params=params)
            items = response.get("Items", [])
            yield items
            if len(items) < PAGE_SIZE:
                break
            params["skip"] += PAGE_SIZE

    async def get_projects(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get all projects."""
        async for projects in self._get_paginated_objects("projects"):
            yield projects

    async def get_deployments(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get all deployments."""
        async for deployments in self._get_paginated_objects("deployments"):
            yield deployments

    async def get_releases(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get all releases."""
        async for releases in self._get_paginated_objects("releases"):
            yield releases

    async def get_targets(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get all targets."""
        async for targets in self._get_paginated_objects("machines"):
            yield targets

    async def get_single_entity(
        self, entity_kind: str, entity_id: str
    ) -> dict[str, Any]:
        """Get a single entity by kind and ID."""
        return await self._send_api_request(f"{entity_kind}/{entity_id}")

    async def get_all_spaces(self) -> list[dict[str, Any]]:
        """Get all spaces in the Octopus instance."""
        return await self._send_api_request("spaces/all")

    async def _create_subscription(self, space_id: str, app_host: str) -> None:
        """Create a new subscription for a space."""
        endpoint = "subscriptions"
        subscription_data = {
            "EventNotificationSubscription": {
                "WebhookURI": f"{app_host}/integration/webhook",
                "WebhookTimeout": "00:00:50",
            },
            "IsDisabled": False,
            "Name": "Port Subscription",
            "SpaceId": f"{space_id}",
        }
        logger.info(
            f"Webhook Subscription - '{subscription_data['Name']}' created successfully."
        )
        return await self._send_api_request(
            endpoint, json_data=subscription_data, method="POST"
        )

    async def create_subscription(self, app_host: str) -> dict[str, Any]:
        """Create a new subscription."""
        for space in await self.get_all_spaces():
            await self._create_subscription(space["Id"], app_host)
        return {"ok": True}

    async def get_subscriptions(self) -> list[dict[str, Any]]:
        """Get existing subscriptions."""
        response = await self._send_api_request("subscriptions/all")
        logger.info(f"Retrieved {len(response)} subscriptions.")
        return response
