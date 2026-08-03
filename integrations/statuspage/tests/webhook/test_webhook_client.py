from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest

from webhook.webhook_client import StatuspageWebhookClient


async def _async_iter(
    items: list[list[dict[str, str]]],
) -> AsyncGenerator[list[dict[str, str]], None]:
    for item in items:
        yield item


@pytest.mark.asyncio
async def test_create_webhook_if_not_exists_filters_webhook_subscribers() -> None:
    client = MagicMock()
    client.pages_base_endpoint = "https://api.statuspage.io/v1/pages"
    client._get_paginated_resources = MagicMock(
        return_value=_async_iter(
            [
                [
                    {"mode": "email", "email": "foo@example.com"},
                    {"endpoint": "https://other.example.com/webhook"},
                ]
            ]
        )
    )
    client.client.post = AsyncMock()

    webhook_client = StatuspageWebhookClient(client)
    await webhook_client.create_webhook_if_not_exists(
        "page-id", "https://app.example.com"
    )

    client._get_paginated_resources.assert_called_once_with(
        "https://api.statuspage.io/v1/pages/page-id/subscribers",
        {"type": "webhook"},
    )
    client.client.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_webhook_if_not_exists_skips_when_webhook_exists() -> None:
    client = MagicMock()
    client.pages_base_endpoint = "https://api.statuspage.io/v1/pages"
    webhook_url = "https://app.example.com/integration/webhook"
    client._get_paginated_resources = MagicMock(
        return_value=_async_iter([[{"endpoint": webhook_url}]])
    )
    client.client.post = AsyncMock()

    webhook_client = StatuspageWebhookClient(client)
    await webhook_client.create_webhook_if_not_exists(
        "page-id", "https://app.example.com"
    )

    client.client.post.assert_not_awaited()
