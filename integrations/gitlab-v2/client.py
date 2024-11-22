import asyncio
from typing import Any

import httpx
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.utils import http_async_client


class GitLabHandler:
    def __init__(
        self,
        host: str | None,
        gitlab_token: str,
        gitlab_url: str,
        webhook_secret: str | None,
    ) -> None:
        self.client = http_async_client
        self.app_host = host
        self.gitlab_baseurl = gitlab_url
        self.token = gitlab_token
        self.webhook_secret = webhook_secret
        self.headers = {"Authorization": f"Bearer {self.token}"}

    async def send_gitlab_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        payload: dict[str, Any] = {},
    ) -> list[dict[str, Any]] | dict[str, Any]:
        url = f"{self.gitlab_baseurl}/{endpoint}"
        logger.info(f"Sending {method} request to Gitlab API: {url}")

        try:
            response = await self.client.request(
                headers=self.headers,
                json=payload,
                method=method,
                url=url,
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Encountered an HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )

            retry_after = e.response.headers.get("Retry-After")
            if retry_after:
                logger.error(
                    f"Request limit exceeded, retrying after {retry_after} seconds..."
                )
                await asyncio.sleep(int(retry_after))

            return []
        except httpx.HTTPError as e:
            logger.error(
                f"Encountered an HTTP error {e} while sending a {method} request to {url}"
            )
            return []

    async def create_webhook(self, group_id: str) -> None:
        webhook_url = f"{self.app_host}/integration/webhook"
        webhook_payload = {
            "url": webhook_url,
            "custom_headers": [{"key": "port-headers", "value": self.webhook_secret}],
            "issues_events": True,
            "merge_requests_events": True,
        }
        endpoint = f"groups/{group_id}/hooks"

        logger.info(f"Fetching hooks for group: {group_id}")
        result = await self.send_gitlab_api_request(endpoint)

        port_hook = next((item for item in result if item["url"] == webhook_url), None)
        if not port_hook:
            logger.info(f"Creating port hook for group: {group_id}")
            await self.send_gitlab_api_request(
                endpoint, method="POST", payload=webhook_payload
            )
        else:
            logger.info(
                f"Port hook already exist. Skipping port hook creation for group: {group_id}"
            )


async def get_gitlab_handler() -> GitLabHandler:
    return GitLabHandler(
        host=ocean.integration_config.get("app_host"),
        gitlab_token=ocean.integration_config["gitlab_token"],
        gitlab_url=ocean.integration_config["gitlab_url"],
        webhook_secret=ocean.integration_config.get("webhook_secret"),
    )
