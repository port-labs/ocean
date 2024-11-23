import asyncio
from typing import Any, AsyncGenerator, Optional

import httpx
from httpx._models import Response as HttpxResponse
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

    async def handle_rate_limit(
        self,
        endpoint: str,
        method: str,
        payload: Optional[dict[str, Any]],
        retry_after: str,
    ) -> None:
        logger.error(f"Request limit exceeded, retrying after {retry_after} seconds...")
        await asyncio.sleep(int(retry_after))
        await self.send_gitlab_api_request(endpoint, method, payload)

    async def send_gitlab_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        payload: Optional[dict[str, Any]] = None,
        query_params: Optional[dict[str, Any]] = None,
    ) -> HttpxResponse:
        url = f"{self.gitlab_baseurl}/{endpoint}"
        logger.info(
            f"URL: {url}, Method: {method}, Params: {query_params}, Payload: {payload}"
        )

        try:
            response = await self.client.request(
                headers=self.headers,
                json=payload,
                method=method,
                params=query_params,
                url=url,
            )
            response.raise_for_status()
            return response

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Encountered an HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )

            retry_after = e.response.headers.get("Retry-After")
            if e.response.status_code == 429 and retry_after:
                await self.handle_rate_limit(endpoint, method, payload, retry_after)
            else:
                raise e
        except httpx.HTTPError as e:
            logger.error(
                f"Encountered an HTTP error {e} while sending a {method} request to {url}"
            )
            raise e

    async def get_paginated_resource(
        self,
        endpoint: str,
        query_params: Optional[dict[str, Any]] = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        page = 1
        while page:
            logger.info(f"Fetching page {page} data from {endpoint}...")

            query_params = query_params or {}
            query_params.update({"page": page})

            response = await self.send_gitlab_api_request(
                endpoint, query_params=query_params
            )
            yield response.json()

            page = response.headers.get("x-next-page")

    async def get_all_resource(self, endpoint: str) -> list[dict[str, Any]]:
        records = []
        async for record in self.get_paginated_resource(endpoint):
            records.extend(record)

        return records

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

        hooks = await self.get_all_resource(endpoint)
        port_hook = next((hook for hook in hooks if hook["url"] == webhook_url), None)
        if not port_hook:
            logger.info(f"Creating port hook for group: {group_id}")
            response = await self.send_gitlab_api_request(
                endpoint, method="POST", payload=webhook_payload
            )
            return response.json()
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
