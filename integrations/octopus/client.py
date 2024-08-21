from typing import Any, AsyncGenerator, Optional
from loguru import logger
from port_ocean.utils import http_async_client
from httpx import HTTPStatusError, Timeout

PAGE_SIZE = 50
WEBHOOK_TIMEOUT = "00:00:50"
CLIENT_TIMEOUT = 60


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
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch paginated data from the Octopus Deploy API."""
        if params is None:
            params = {}
        params["skip"] = 0
        params["take"] = PAGE_SIZE
        page = 0
        while True:
            response = await self._send_api_request(f"{kind}s", params=params)
            items = response.get("Items", [])
            last_page = response.get("LastPageNumber", 0)
            yield items
            if page >= last_page:
                break
            if kind == 'release' and skip >= 100:
                break
            params["skip"] += PAGE_SIZE
            page += 1

    async def get_single_resource(
        self, resource_kind: str, resource_id: str
    ) -> dict[str, Any]:
        """Get a single resource by kind and ID."""
        return await self._send_api_request(f"{resource_kind}/{resource_id}")

    async def _get_all_spaces(self) -> list[dict[str, Any]]:
        """Get all spaces in the Octopus instance."""
        return await self._send_api_request("spaces/all")

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
            "Name": f"Port Subscription - {space_id}",
            "SpaceId": space_id,
        }
        logger.info(
            f"Creating Webhook Subscription - '{subscription_data['Name']}' in '{space_id}'"
        )
        return await self._send_api_request(
            endpoint, json_data=subscription_data, method="POST"
        )

    async def create_webhook_subscription(self, app_host: str) -> dict[str, Any]:
        """Create a new subscription for all spaces."""
        for space in await self._get_all_spaces():
            try:
                response = await self._create_subscription(space["Id"], app_host)
                if response.get("Id"):
                    logger.info(
                        f"Subscription created for space '{space['Id']}' with ID {response['Id']}"
                    )
                else:
                    logger.error(
                        f"Failed to create subscription for space '{space['Id']}'"
                    )
            except Exception as e:
                logger.error(f"Unexpected error for space '{space['Id']}': {str(e)}")
        return {"ok": True}

    async def get_webhook_subscriptions(self) -> list[dict[str, Any]]:
        """Get existing subscriptions."""
        response = await self._send_api_request("subscriptions/all")
        logger.info(f"Retrieved {len(response)} subscriptions.")
        return response
