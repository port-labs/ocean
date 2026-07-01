from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from client import FirehydrantClient


@pytest.fixture
def client() -> FirehydrantClient:
    with patch("client.http_async_client", MagicMock()):
        return FirehydrantClient("https://api.firehydrant.io", "test-token")


class TestBuildWebhookTargetUrl:
    @pytest.mark.parametrize(
        "base_url,expected",
        [
            ("https://ocean.example.com", "https://ocean.example.com/integration/webhook"),
            (
                "https://ocean.example.com/",
                "https://ocean.example.com/integration/webhook",
            ),
            (
                "https://ocean.example.com/prefix",
                "https://ocean.example.com/prefix/integration/webhook",
            ),
            (
                "https://ocean.example.com/prefix/",
                "https://ocean.example.com/prefix/integration/webhook",
            ),
        ],
    )
    def test_build_webhook_target_url_normalizes_base_url(
        self, base_url: str, expected: str
    ) -> None:
        assert FirehydrantClient._build_webhook_target_url(base_url) == expected


@pytest.mark.asyncio
class TestCreateWebhooksIfNotExists:
    async def _mock_paginated_webhooks(
        self, webhooks: list[dict[str, Any]]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        yield webhooks

    async def test_skips_creation_when_existing_webhook_matches_normalized_url(
        self, client: FirehydrantClient
    ) -> None:
        existing_webhooks = [
            {"url": "https://ocean.example.com/integration/webhook/"}
        ]

        with (
            patch.object(
                client,
                "get_paginated_resource",
                return_value=self._mock_paginated_webhooks(existing_webhooks),
            ),
            patch.object(client, "send_api_request", new_callable=AsyncMock) as mock_send,
        ):
            await client.create_webhooks_if_not_exists("https://ocean.example.com/")

        mock_send.assert_not_called()

    async def test_creates_webhook_with_normalized_target_url(
        self, client: FirehydrantClient
    ) -> None:
        with (
            patch.object(
                client,
                "get_paginated_resource",
                return_value=self._mock_paginated_webhooks([]),
            ),
            patch.object(client, "send_api_request", new_callable=AsyncMock) as mock_send,
        ):
            await client.create_webhooks_if_not_exists("https://ocean.example.com/")

        mock_send.assert_awaited_once_with(
            endpoint="webhooks",
            method="POST",
            json_data={
                "url": "https://ocean.example.com/integration/webhook",
                "state": "active",
                "subscriptions": ["incidents", "change_events"],
            },
        )
