from loguru import logger

from client import StatusPageClient
from webhook.consts import WEBHOOK_PATH


class StatuspageWebhookClient:
    """Manages Statuspage webhook subscriptions for live events."""

    def __init__(self, client: StatusPageClient) -> None:
        self._client = client

    def _webhook_url(self, app_host: str) -> str:
        return f"{app_host}/integration{WEBHOOK_PATH}"

    async def create_webhook_if_not_exists(self, page_id: str, app_host: str) -> None:
        webhook_url = self._webhook_url(app_host)
        async for webhooks in self._client._get_paginated_resources(
            f"{self._client.pages_base_endpoint}/{page_id}/subscribers",
            {"type": "webhook"},
        ):
            if any(webhook.get("endpoint") == webhook_url for webhook in webhooks):
                logger.info(f"Webhook already exists for page: {page_id}")
                return

        logger.info(
            f"Creating webhook subscription for page: {page_id} with endpoint: {webhook_url}"
        )
        result = await self._client.client.post(
            f"{self._client.pages_base_endpoint}/{page_id}/subscribers",
            json={"subscriber": {"endpoint": webhook_url}},
        )

        if result.status_code == 201:
            logger.info(f"Webhook created successfully for page: {page_id}")
        else:
            logger.error(
                f"Result from creating webhook for page {page_id}: ({result.status_code}) {result.text}"
            )

    async def create_webhooks_for_all_pages(self, app_host: str) -> None:
        pages = self._client.statuspage_ids or [
            page["id"] for page in await self._client.get_pages()
        ]
        logger.info(f"Creating webhooks for pages: {pages}")
        for page_id in pages:
            await self.create_webhook_if_not_exists(page_id, app_host)
